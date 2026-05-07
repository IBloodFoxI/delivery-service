import json
import datetime
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import FileResponse
from django.db.models import Sum, Count
from django.utils import timezone
from .models import SupportTicket, TicketMessage
from .forms import TicketReplyForm
from apps.orders.models import Order, Delivery


def support_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_support or request.user.is_admin_role or request.user.is_staff):
            messages.error(request, 'Недостаточно прав')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


def _chart_data(days=14):
    today = timezone.now().date()
    labels, orders_data, revenue_data, tickets_data = [], [], [], []
    for i in range(days - 1, -1, -1):
        day = today - datetime.timedelta(days=i)
        labels.append(day.strftime('%d.%m'))
        orders_data.append(Order.objects.filter(created_at__date=day).count())
        rev = Order.objects.filter(created_at__date=day, status='delivered').aggregate(
            t=Sum('total_price')
        )['t'] or 0
        revenue_data.append(float(rev))
        tickets_data.append(SupportTicket.objects.filter(created_at__date=day).count())
    return labels, orders_data, revenue_data, tickets_data


@support_required
def dashboard(request):
    open_tickets = SupportTicket.objects.filter(
        status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS]
    ).select_related('user', 'order').order_by('-created_at')
    stats = {
        'open': SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count(),
        'in_progress': SupportTicket.objects.filter(status=SupportTicket.Status.IN_PROGRESS).count(),
        'closed_today': SupportTicket.objects.filter(status=SupportTicket.Status.CLOSED).count(),
        'active_deliveries': Order.objects.filter(
            status__in=[Order.Status.ASSIGNED, Order.Status.IN_PROGRESS]
        ).count(),
    }
    labels, orders_data, revenue_data, tickets_data = _chart_data()
    return render(request, 'support_panel/dashboard.html', {
        'open_tickets': open_tickets,
        'stats': stats,
        'chart_labels': json.dumps(labels),
        'chart_orders': json.dumps(orders_data),
        'chart_revenue': json.dumps(revenue_data),
        'chart_tickets': json.dumps(tickets_data),
    })


@support_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        form = TicketReplyForm(request.POST)
        if form.is_valid():
            TicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                message=form.cleaned_data['message']
            )
            ticket.status = SupportTicket.Status.IN_PROGRESS
            ticket.assigned_to = request.user
            ticket.save()
            return redirect('support_panel:ticket_detail', ticket_id=ticket.id)
    else:
        form = TicketReplyForm()
    msgs = ticket.messages.select_related('author').all()
    return render(request, 'support_panel/ticket_detail.html', {
        'ticket': ticket,
        'msgs': msgs,
        'form': form,
    })


@support_required
def close_ticket(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        ticket.status = SupportTicket.Status.CLOSED
        ticket.save()
        messages.success(request, f'Тикет #{ticket.id} закрыт')
    return redirect('support_panel:dashboard')


@support_required
def deliveries_list(request):
    status_filter = request.GET.get('status', '')
    orders = Order.objects.select_related('user', 'courier').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'support_panel/deliveries_list.html', {
        'orders': orders,
        'statuses': Order.Status.choices,
        'status_filter': status_filter,
    })


@support_required
def cancel_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        if order.status in [Order.Status.DELIVERED, Order.Status.CANCELLED]:
            messages.error(request, 'Невозможно отменить завершённый заказ')
        else:
            from apps.accounts.models import BalanceTransaction
            from django.db import transaction
            with transaction.atomic():
                order.status = Order.Status.CANCELLED
                order.save()
                # Возврат средств покупателю
                order.user.balance += order.total_price
                order.user.save(update_fields=['balance'])
                BalanceTransaction.objects.create(
                    user=order.user,
                    amount=order.total_price,
                    transaction_type=BalanceTransaction.TransactionType.REFUND,
                    description=f'Возврат за отменённый заказ #{order.id}'
                )
            messages.success(request, f'Заказ #{order.id} отменён, средства возвращены')
    return redirect('support_panel:deliveries_list')


@support_required
def export_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold_font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', bold_font_path))
        FONT_NORMAL = 'DejaVu'
        FONT_BOLD = 'DejaVu-Bold'
    else:
        FONT_NORMAL = 'Helvetica'
        FONT_BOLD = 'Helvetica-Bold'

    now = timezone.now()
    last_30 = now - datetime.timedelta(days=30)

    orders_total = Order.objects.filter(created_at__gte=last_30).count()
    orders_delivered = Order.objects.filter(created_at__gte=last_30, status='delivered').count()
    orders_cancelled = Order.objects.filter(created_at__gte=last_30, status='cancelled').count()
    revenue = Order.objects.filter(
        created_at__gte=last_30, status='delivered'
    ).aggregate(t=Sum('total_price'))['t'] or 0

    tickets_open = SupportTicket.objects.filter(status='open').count()
    tickets_closed = SupportTicket.objects.filter(status='closed').count()
    tickets_total = SupportTicket.objects.count()

    labels, orders_data, revenue_data, tickets_data = _chart_data(30)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    styles['Title'].fontName = FONT_BOLD
    styles['Normal'].fontName = FONT_NORMAL
    styles['Heading2'].fontName = FONT_BOLD
    story = []

    story.append(Paragraph('Отчёт — Доставка МИГ', styles['Title']))
    story.append(Paragraph(f'Дата формирования: {now.strftime("%d.%m.%Y %H:%M")}', styles['Normal']))
    story.append(Spacer(1, 16))

    story.append(Paragraph('Заказы (последние 30 дней)', styles['Heading2']))
    order_table_data = [
        ['Показатель', 'Значение'],
        ['Всего заказов', str(orders_total)],
        ['Доставлено', str(orders_delivered)],
        ['Отменено', str(orders_cancelled)],
        ['Выручка (₽)', f'{float(revenue):,.2f}'],
    ]
    t = Table(order_table_data, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#198754')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 16))

    story.append(Paragraph('Тикеты поддержки', styles['Heading2']))
    ticket_table_data = [
        ['Показатель', 'Значение'],
        ['Всего тикетов', str(tickets_total)],
        ['Открытых', str(tickets_open)],
        ['Закрытых', str(tickets_closed)],
    ]
    t2 = Table(ticket_table_data, colWidths=[300, 150])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 16))

    story.append(Paragraph('Заказы по дням (последние 30 дней)', styles['Heading2']))
    daily_data = [['Дата', 'Заказов', 'Выручка (₽)']]
    for label, cnt, rev in zip(labels, orders_data, revenue_data):
        daily_data.append([label, str(cnt), f'{rev:,.2f}'])
    t3 = Table(daily_data, colWidths=[150, 100, 200])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT_NORMAL),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t3)

    doc.build(story)
    buffer.seek(0)
    filename = f'report_{now.strftime("%Y%m%d_%H%M")}.pdf'
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
