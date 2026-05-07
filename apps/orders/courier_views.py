import math
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Order, Delivery


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(float(lat1)))
         * math.cos(math.radians(float(lat2)))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def courier_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_courier:
            messages.error(request, 'Эта страница только для курьеров')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@courier_required
def dashboard(request):
    active_orders = Order.objects.filter(
        courier=request.user,
        status__in=[Order.Status.ASSIGNED, Order.Status.IN_PROGRESS]
    ).select_related('user').prefetch_related('items')

    completed_orders = Order.objects.filter(
        courier=request.user,
        status=Order.Status.DELIVERED
    ).order_by('-updated_at')[:10]

    pending_qs = Order.objects.filter(
        status=Order.Status.PENDING,
        courier__isnull=True
    ).select_related('user')

    courier = request.user
    all_pending = list(pending_qs[:50])

    import json as _json
    from django.conf import settings as _settings

    if courier.courier_lat and courier.courier_lon:
        for o in all_pending:
            if o.addr_lat and o.addr_lon:
                dist = _haversine_km(
                    courier.courier_lat, courier.courier_lon,
                    o.addr_lat, o.addr_lon
                )
                o.distance_km = round(dist, 1)
                o.in_range = dist <= 10
            else:
                o.distance_km = None
                o.in_range = True  # без координат — доступен всем

        # Ближние сначала, дальние в конец
        all_pending.sort(key=lambda o: o.distance_km if o.distance_km is not None else 9999)
    else:
        for o in all_pending:
            o.distance_km = None
            o.in_range = None  # геолокация не определена — статус неизвестен

    available_orders = all_pending[:20]

    map_orders = [
        {
            'id': o.id,
            'lat': float(o.addr_lat),
            'lon': float(o.addr_lon),
            'address': o.delivery_address,
            'in_range': getattr(o, 'in_range', True),
        }
        for o in all_pending if o.addr_lat and o.addr_lon
    ]

    return render(request, 'courier/dashboard.html', {
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'available_orders': available_orders,
        'has_location': bool(courier.courier_lat and courier.courier_lon),
        # courier_lat/lon больше не используются для инициализации карты
        # (карта стартует с нейтральной точки, watchPosition обновляет сразу)
        'map_orders_json': _json.dumps(map_orders),
        'ymaps_key': _settings.YANDEX_MAPS_KEY,
    })


@courier_required
def accept_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, status=Order.Status.PENDING)
    if request.method == 'POST':
        order.courier = request.user
        order.status = Order.Status.ASSIGNED
        order.save()
        Delivery.objects.get_or_create(order=order, defaults={'courier': request.user})
        messages.success(request, f'Заказ #{order.id} принят')
    return redirect('courier:dashboard')


@courier_required
def start_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, courier=request.user, status=Order.Status.ASSIGNED)
    if request.method == 'POST':
        order.status = Order.Status.IN_PROGRESS
        order.save()
        delivery = order.delivery
        delivery.started_at = timezone.now()
        delivery.save()
        messages.success(request, 'Доставка начата')
    return redirect('courier:dashboard')


@courier_required
def complete_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, courier=request.user, status=Order.Status.IN_PROGRESS)
    if request.method == 'POST':
        from apps.accounts.models import BalanceTransaction
        earning = (order.total_price - order.delivery_fee) * Decimal('0.10') + order.delivery_fee
        earning = earning.quantize(Decimal('0.01'))
        with transaction.atomic():
            order.status = Order.Status.DELIVERED
            order.save(update_fields=['status'])
            delivery = order.delivery
            delivery.completed_at = timezone.now()
            delivery.save(update_fields=['completed_at'])
            request.user.balance += earning
            request.user.save(update_fields=['balance'])
            BalanceTransaction.objects.create(
                user=request.user,
                amount=earning,
                transaction_type=BalanceTransaction.TransactionType.EARNING,
                description=f'Заработок за заказ #{order.id} (10% + доставка)',
            )
        messages.success(request, f'Заказ #{order.id} доставлен! Начислено {earning} ₽')
    return redirect('courier:dashboard')


@courier_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, courier=request.user)
    return render(request, 'courier/order_detail.html', {'order': order})


@courier_required
def wallet(request):
    from apps.accounts.models import BalanceTransaction, WithdrawalRequest
    transactions = BalanceTransaction.objects.filter(
        user=request.user,
        transaction_type__in=[
            BalanceTransaction.TransactionType.EARNING,
            BalanceTransaction.TransactionType.WITHDRAWAL,
        ]
    ).order_by('-created_at')[:30]
    withdrawals = WithdrawalRequest.objects.filter(courier=request.user).order_by('-created_at')[:10]
    return render(request, 'courier/wallet.html', {
        'transactions': transactions,
        'withdrawals': withdrawals,
    })


@require_POST
@courier_required
def request_withdrawal(request):
    from apps.accounts.models import BalanceTransaction, WithdrawalRequest
    from django.conf import settings
    try:
        amount = Decimal(request.POST.get('amount', '0'))
    except Exception:
        messages.error(request, 'Некорректная сумма')
        return redirect('courier:wallet')

    if amount <= 0:
        messages.error(request, 'Сумма должна быть больше 0')
        return redirect('courier:wallet')

    if request.user.balance < amount:
        messages.error(request, f'Недостаточно средств. Доступно: {request.user.balance} ₽')
        return redirect('courier:wallet')

    phone = request.POST.get('phone', request.user.phone_number).strip()

    payout_id = ''
    payout_error = None
    if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
        try:
            from yookassa import Configuration
            from yookassa.domain.models import Payout
            Configuration.account_id = settings.YOOKASSA_SHOP_ID
            Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
            payout = Payout.create({
                'amount': {'value': str(amount), 'currency': 'RUB'},
                'payout_destination_data': {'type': 'sbp', 'phone': phone},
                'description': f'Вывод заработка — {request.user.full_name}',
            })
            payout_id = payout.id
        except Exception as e:
            payout_error = str(e)

    with transaction.atomic():
        wr = WithdrawalRequest.objects.create(
            courier=request.user,
            amount=amount,
            phone=phone,
            yookassa_payout_id=payout_id,
            status=WithdrawalRequest.Status.DONE if payout_id else WithdrawalRequest.Status.PENDING,
        )
        if payout_id:
            request.user.balance -= amount
            request.user.save(update_fields=['balance'])
            BalanceTransaction.objects.create(
                user=request.user,
                amount=-amount,
                transaction_type=BalanceTransaction.TransactionType.WITHDRAWAL,
                description=f'Вывод через ЮКассу (ID: {payout_id[:12]})',
            )
            messages.success(request, f'Вывод {amount} ₽ на {phone} отправлен!')
        else:
            msg = f'Заявка на вывод {amount} ₽ создана. Обработаем вручную.'
            if payout_error:
                msg += f' (авто-выплата недоступна: {payout_error})'
            messages.info(request, msg)
    return redirect('courier:wallet')


@require_POST
@courier_required
def update_location(request):
    try:
        data = json.loads(request.body)
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        request.user.courier_lat = lat
        request.user.courier_lon = lon
        request.user.courier_location_at = timezone.now()
        request.user.save(update_fields=['courier_lat', 'courier_lon', 'courier_location_at'])
        return JsonResponse({'ok': True})
    except Exception:
        return JsonResponse({'ok': False}, status=400)
