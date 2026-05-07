from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.conf import settings
from .models import User, WithdrawalRequest
from apps.orders.models import Order, Delivery
from apps.support.models import SupportTicket
from apps.catalog.models import Product, Category
from apps.catalog.forms import ProductForm
from apps.support.panel_views import export_pdf as _support_export_pdf


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_admin_role or request.user.is_staff):
            messages.error(request, 'Недостаточно прав')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def export_pdf(request):
    return _support_export_pdf(request)


@admin_required
def dashboard(request):
    stats = {
        'total_users': User.objects.count(),
        'total_orders': Order.objects.count(),
        'active_deliveries': Delivery.objects.filter(
            order__status__in=[Order.Status.ASSIGNED, Order.Status.IN_PROGRESS]
        ).count(),
        'total_revenue': Order.objects.filter(
            status=Order.Status.DELIVERED
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'couriers': User.objects.filter(role=User.Role.COURIER).count(),
        'pending_orders': Order.objects.filter(status=Order.Status.PENDING).count(),
    }
    recent_orders = Order.objects.select_related('user', 'courier').order_by('-created_at')[:10]
    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats,
        'recent_orders': recent_orders,
    })


@admin_required
def users_list(request):
    role_filter = request.GET.get('role', '')
    search = request.GET.get('search', '')
    users = User.objects.all().order_by('-date_joined')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        users = users.filter(
            Q(full_name__icontains=search)
        )
    return render(request, 'admin_panel/users_list.html', {
        'users': users,
        'roles': User.Role.choices,
        'role_filter': role_filter,
        'search': search,
    })


@admin_required
def change_user_role(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in [r[0] for r in User.Role.choices]:
            if user == request.user and new_role != User.Role.ADMIN:
                messages.error(request, 'Нельзя сменить роль самому себе')
            else:
                user.role = new_role
                if new_role == User.Role.ADMIN:
                    user.is_staff = True
                else:
                    user.is_staff = False
                user.save()
                messages.success(request, f'Роль пользователя {user.full_name} изменена на {user.get_role_display()}')
        return redirect('admin_panel:users_list')
    return redirect('admin_panel:users_list')


@admin_required
def orders_list(request):
    status_filter = request.GET.get('status', '')
    orders = Order.objects.select_related('user', 'courier').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)
    return render(request, 'admin_panel/orders_list.html', {
        'orders': orders,
        'statuses': Order.Status.choices,
        'status_filter': status_filter,
    })


@admin_required
def change_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in [s[0] for s in Order.Status.choices]:
            order.status = new_status
            order.save()
            messages.success(request, f'Статус заказа #{order.id} изменён')
    return redirect('admin_panel:orders_list')


@admin_required
def cancel_order(request, order_id):
    """Отмена заказа с автовозвратом через ЮКассу."""
    if request.method != 'POST':
        return redirect('admin_panel:orders_list')
    order = get_object_or_404(Order, id=order_id)
    if order.status in (Order.Status.DELIVERED, Order.Status.CANCELLED):
        messages.error(request, 'Нельзя отменить завершённый или уже отменённый заказ')
        return redirect('admin_panel:orders_list')

    refund_done = False
    if order.yookassa_payment_id and settings.YOOKASSA_SHOP_ID:
        try:
            from yookassa import Configuration
            from yookassa.domain.models import Refund
            Configuration.account_id = settings.YOOKASSA_SHOP_ID
            Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
            Refund.create({
                'payment_id': order.yookassa_payment_id,
                'amount': {'value': str(order.total_price), 'currency': 'RUB'},
                'description': f'Отмена заказа #{order.id}',
            })
            refund_done = True
        except Exception as e:
            messages.warning(request, f'Возврат через ЮКассу не удался: {e}. Заказ всё равно отменён.')

    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status'])
    msg = f'Заказ #{order.id} отменён'
    if refund_done:
        msg += '. Возврат средств отправлен через ЮКассу.'
    messages.success(request, msg)
    return redirect('admin_panel:orders_list')


@admin_required
def revenue(request):
    from django.utils import timezone
    import datetime
    today = timezone.now().date()
    month_start = today.replace(day=1)

    total_revenue = Order.objects.filter(status=Order.Status.DELIVERED).aggregate(t=Sum('total_price'))['t'] or 0
    month_revenue = Order.objects.filter(
        status=Order.Status.DELIVERED, created_at__date__gte=month_start
    ).aggregate(t=Sum('total_price'))['t'] or 0
    today_revenue = Order.objects.filter(
        status=Order.Status.DELIVERED, created_at__date=today
    ).aggregate(t=Sum('total_price'))['t'] or 0

    courier_earnings = []
    couriers = User.objects.filter(role=User.Role.COURIER, is_active=True)
    for c in couriers:
        earned = c.transactions.filter(
            transaction_type='earning'
        ).aggregate(t=Sum('amount'))['t'] or 0
        courier_earnings.append({'courier': c, 'earned': earned})
    courier_earnings.sort(key=lambda x: x['earned'], reverse=True)

    recent = Order.objects.filter(status=Order.Status.DELIVERED).order_by('-updated_at')[:20]
    withdrawals = WithdrawalRequest.objects.filter(status='pending').select_related('courier')

    return render(request, 'admin_panel/revenue.html', {
        'total_revenue': total_revenue,
        'month_revenue': month_revenue,
        'today_revenue': today_revenue,
        'courier_earnings': courier_earnings,
        'recent': recent,
        'withdrawals': withdrawals,
    })


@admin_required
def process_withdrawal(request, wr_id):
    if request.method != 'POST':
        return redirect('admin_panel:revenue')
    wr = get_object_or_404(WithdrawalRequest, id=wr_id)
    from apps.accounts.models import BalanceTransaction
    from django.utils import timezone as tz
    action = request.POST.get('action')
    if action == 'approve':
        with __import__('django').db.transaction.atomic():
            wr.status = WithdrawalRequest.Status.DONE
            wr.processed_at = tz.now()
            wr.admin_note = request.POST.get('note', '')
            wr.save()
            wr.courier.balance -= wr.amount
            wr.courier.save(update_fields=['balance'])
            BalanceTransaction.objects.create(
                user=wr.courier,
                amount=-wr.amount,
                transaction_type=BalanceTransaction.TransactionType.WITHDRAWAL,
                description=f'Вывод средств (заявка #{wr.id}, обработано администратором)',
            )
        messages.success(request, f'Вывод {wr.amount} ₽ для {wr.courier.full_name} подтверждён')
    elif action == 'reject':
        wr.status = WithdrawalRequest.Status.REJECTED
        wr.processed_at = tz.now()
        wr.admin_note = request.POST.get('note', '')
        wr.save()
        messages.info(request, f'Вывод {wr.amount} ₽ отклонён')
    return redirect('admin_panel:revenue')


@admin_required
def tickets_list(request):
    status_filter = request.GET.get('status', '')
    tickets = SupportTicket.objects.select_related('user', 'order', 'assigned_to').order_by('-created_at')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    return render(request, 'admin_panel/tickets_list.html', {
        'tickets': tickets,
        'statuses': SupportTicket.Status.choices,
        'status_filter': status_filter,
    })


@admin_required
def deliveries_list(request):
    deliveries = Delivery.objects.select_related('order', 'order__user', 'courier').order_by('-order__created_at')
    return render(request, 'admin_panel/deliveries_list.html', {'deliveries': deliveries})


@admin_required
def products_list(request):
    products = Product.objects.select_related('category').order_by('category', 'name')
    return render(request, 'admin_panel/products_list.html', {'products': products})


@admin_required
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Товар добавлен')
            return redirect('admin_panel:products_list')
    else:
        form = ProductForm()
    return render(request, 'admin_panel/product_form.html', {'form': form, 'title': 'Добавить товар'})


@admin_required
def product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Товар обновлён')
            return redirect('admin_panel:products_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'admin_panel/product_form.html', {'form': form, 'title': 'Редактировать товар', 'product': product})


@admin_required
def product_toggle(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_available = not product.is_available
    product.save()
    status = 'доступен' if product.is_available else 'недоступен'
    messages.success(request, f'Товар «{product.name}» теперь {status}')
    return redirect('admin_panel:products_list')


@admin_required
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Товар «{name}» удалён')
    return redirect('admin_panel:products_list')




# ── Backup views ─────────────────────────────────────────────────────────────

@admin_required
def backup_list(request):
    from apps.backup.models import BackupRecord, BackupSettings
    records = BackupRecord.objects.all()
    cfg = BackupSettings.get()
    return render(request, 'admin_panel/backup.html', {
        'records': records,
        'cfg': cfg,
        'frequency_choices': BackupSettings.Frequency.choices,
    })


@admin_required
def backup_create(request):
    if request.method == 'POST':
        from django.core.management import call_command
        try:
            notes = request.POST.get('notes', 'Ручной бэкап')
            call_command('backup_db', notes=notes)
            messages.success(request, 'Резервная копия создана успешно')
        except Exception as e:
            messages.error(request, f'Ошибка создания резервной копии: {e}')
    return redirect('admin_panel:backup_list')


@admin_required
def backup_download(request, record_id):
    import os
    from django.http import FileResponse, Http404
    from django.conf import settings
    from apps.backup.models import BackupRecord
    record = get_object_or_404(BackupRecord, id=record_id)
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    filepath = os.path.join(backup_dir, record.filename)
    if not os.path.exists(filepath):
        raise Http404('Файл не найден')
    response = FileResponse(open(filepath, 'rb'), content_type='application/gzip')
    response['Content-Disposition'] = f'attachment; filename="{record.filename}"'
    return response


@admin_required
def backup_restore(request, record_id):
    import os
    from django.conf import settings
    from django.core.management import call_command
    from apps.backup.models import BackupRecord
    if request.method != 'POST':
        return redirect('admin_panel:backup_list')
    record = get_object_or_404(BackupRecord, id=record_id)
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    filepath = os.path.join(backup_dir, record.filename)
    if not os.path.exists(filepath):
        messages.error(request, 'Файл резервной копии не найден')
        return redirect('admin_panel:backup_list')
    try:
        call_command('loaddata', filepath)
        messages.success(request, f'База данных восстановлена из {record.filename}')
    except Exception as e:
        messages.error(request, f'Ошибка восстановления: {e}')
    return redirect('admin_panel:backup_list')


@admin_required
def backup_delete(request, record_id):
    import os
    from django.conf import settings
    from apps.backup.models import BackupRecord
    if request.method != 'POST':
        return redirect('admin_panel:backup_list')
    record = get_object_or_404(BackupRecord, id=record_id)
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    filepath = os.path.join(backup_dir, record.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    record.delete()
    messages.success(request, f'Резервная копия {record.filename} удалена')
    return redirect('admin_panel:backup_list')


@admin_required
def backup_settings(request):
    from apps.backup.models import BackupSettings
    if request.method != 'POST':
        return redirect('admin_panel:backup_list')
    cfg = BackupSettings.get()
    cfg.frequency = request.POST.get('frequency', cfg.frequency)
    cfg.is_enabled = 'is_enabled' in request.POST
    try:
        cfg.max_backups = int(request.POST.get('max_backups', cfg.max_backups))
    except ValueError:
        pass
    cfg.save()
    messages.success(request, 'Настройки резервного копирования сохранены')
    return redirect('admin_panel:backup_list')


@admin_required
def backup_sql_create(request):
    if request.method == 'POST':
        from django.core.management import call_command
        try:
            notes = request.POST.get('notes', 'SQL бэкап вручную')
            call_command('backup_sql', notes=notes)
            messages.success(request, 'SQL резервная копия создана успешно')
        except Exception as e:
            messages.error(request, f'Ошибка создания SQL резервной копии: {e}')
    return redirect('admin_panel:backup_list')


@admin_required
def backup_sql_restore(request, record_id):
    import os, gzip, subprocess, tempfile
    from django.conf import settings as _s
    from apps.backup.models import BackupRecord
    if request.method != 'POST':
        return redirect('admin_panel:backup_list')
    record = get_object_or_404(BackupRecord, id=record_id)
    if not record.filename.endswith('.sql.gz'):
        messages.error(request, 'Это не SQL резервная копия')
        return redirect('admin_panel:backup_list')
    backup_dir = getattr(_s, 'BACKUP_DIR', os.path.join(_s.BASE_DIR, 'backups'))
    filepath = os.path.join(backup_dir, record.filename)
    if not os.path.exists(filepath):
        messages.error(request, 'Файл не найден')
        return redirect('admin_panel:backup_list')
    try:
        db = _s.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')
        # Распаковываем во временный файл
        with gzip.open(filepath, 'rb') as gz:
            sql_data = gz.read()
        with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
            tmp.write(sql_data)
            tmp_path = tmp.name
        result = subprocess.run(
            ['psql', '-h', db.get('HOST', 'db'), '-p', str(db.get('PORT', '5432')),
             '-U', db.get('USER', 'postgres'), '-d', db.get('NAME', 'postgres'), '-f', tmp_path],
            capture_output=True, env=env,
        )
        os.unlink(tmp_path)
        if result.returncode != 0:
            messages.error(request, f'Ошибка восстановления: {result.stderr.decode()}')
        else:
            messages.success(request, f'База данных восстановлена из {record.filename}')
    except Exception as e:
        messages.error(request, f'Ошибка: {e}')
    return redirect('admin_panel:backup_list')
