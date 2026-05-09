from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import SupportTicket, TicketMessage
from .forms import TicketCreateForm, TicketReplyForm
from apps.orders.models import Order


@login_required
def create_ticket(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == 'POST':
        form = TicketCreateForm(request.POST)
        if form.is_valid():
            ticket = SupportTicket.objects.create(
                order=order,
                user=request.user,
                subject=form.cleaned_data['subject'],
            )
            TicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                message=form.cleaned_data['first_message']
            )
            messages.success(request, 'Тикет создан. Мы скоро ответим!')
            return redirect('support:ticket_detail', ticket_id=ticket.id)
    else:
        form = TicketCreateForm()
    return render(request, 'support/create_ticket.html', {'form': form, 'order': order})


@login_required
def ticket_detail(request, ticket_id):
    if request.user.is_customer:
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    elif request.user.is_support or request.user.is_admin_role or request.user.is_staff:
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
    else:
        return redirect('home')

    if request.method == 'POST':
        form = TicketReplyForm(request.POST)
        if form.is_valid():
            TicketMessage.objects.create(
                ticket=ticket,
                author=request.user,
                message=form.cleaned_data['message']
            )
            if ticket.status == SupportTicket.Status.OPEN:
                ticket.status = SupportTicket.Status.IN_PROGRESS
                ticket.save()
            return redirect('support:ticket_detail', ticket_id=ticket.id)
    else:
        form = TicketReplyForm()

    msgs = ticket.messages.select_related('author').all()
    return render(request, 'support/ticket_detail.html', {
        'ticket': ticket,
        'msgs': msgs,
        'form': form,
    })


@login_required
def my_tickets(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support/my_tickets.html', {'tickets': tickets})


@login_required
def ticket_msgs_count(request, ticket_id):
    if request.user.is_customer:
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    elif request.user.is_support or request.user.is_admin_role or request.user.is_staff:
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
    else:
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse({'count': ticket.messages.count(), 'status': ticket.status})
