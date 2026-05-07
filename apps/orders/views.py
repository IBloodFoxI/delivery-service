from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.conf import settings
from .models import Cart, CartItem, Order, OrderItem, Delivery, DELIVERY_FEE
from .forms import CheckoutForm
from apps.catalog.models import Product
from apps.accounts.models import BalanceTransaction, User


def customer_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_customer:
            messages.error(request, 'Эта страница только для покупателей')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def cart_view(request):
    if not request.user.is_customer:
        return redirect('home')
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
    return render(request, 'orders/cart.html', {'cart': cart, 'items': items})


@require_POST
@login_required
def add_to_cart(request, product_id):
    if not request.user.is_customer:
        return JsonResponse({'error': 'Только для покупателей'}, status=403)
    product = get_object_or_404(Product, id=product_id, is_available=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart.total_items,
            'message': f'«{product.name}» добавлен в корзину'
        })
    messages.success(request, f'«{product.name}» добавлен в корзину')
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@require_POST
@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('orders:cart')


@require_POST
@login_required
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        item.delete()
    else:
        item.quantity = quantity
        item.save()
    return redirect('orders:cart')


@customer_required
def checkout_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
    if not items.exists():
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('home')

    delivery_fee = Decimal(str(DELIVERY_FEE))

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            cart_total = cart.total_price
            grand_total = cart_total + delivery_fee

            try:
                addr_lat = Decimal(request.POST.get('addr_lat') or '0') or None
                addr_lon = Decimal(request.POST.get('addr_lon') or '0') or None
            except Exception:
                addr_lat = addr_lon = None

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    delivery_address=form.cleaned_data['delivery_address'],
                    addr_lat=addr_lat,
                    addr_lon=addr_lon,
                    comment=form.cleaned_data['comment'],
                    total_price=grand_total,
                    delivery_fee=delivery_fee,
                    status=Order.Status.PAYMENT_PENDING,
                )
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_name=item.product.name,
                        quantity=item.quantity,
                        price=item.product.price,
                    )

            if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
                try:
                    from yookassa import Configuration, Payment as YKPayment
                    Configuration.account_id = settings.YOOKASSA_SHOP_ID
                    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
                    return_url = request.build_absolute_uri(
                        reverse('orders:order_payment_return') + f'?order_id={order.id}'
                    )
                    payment = YKPayment.create({
                        'amount': {'value': str(grand_total), 'currency': 'RUB'},
                        'confirmation': {'type': 'redirect', 'return_url': return_url},
                        'capture': True,
                        'description': f'Заказ #{order.id} — Доставка МИГ',
                        'metadata': {'order_id': order.id},
                    })
                    order.yookassa_payment_id = payment.id
                    order.save(update_fields=['yookassa_payment_id'])
                    return redirect(payment.confirmation.confirmation_url)
                except Exception as e:
                    order.delete()
                    messages.error(request, f'Ошибка платёжной системы: {e}')
                    return render(request, 'orders/checkout.html', {
                        'form': form, 'cart': cart, 'items': items,
                        'delivery_fee': delivery_fee, 'grand_total': grand_total,
                        'ymaps_key': settings.YANDEX_MAPS_KEY,
                    })
            else:
                # Тестовый режим — моментальное подтверждение
                order.status = Order.Status.PENDING
                order.save(update_fields=['status'])
                cart.items.all().delete()
                _notify_couriers_new_order(order)
                messages.success(request, f'Заказ #{order.id} оформлен! (тестовый режим)')
                return redirect('orders:order_detail', order_id=order.id)
    else:
        form = CheckoutForm()

    cart_total = cart.total_price
    grand_total = cart_total + delivery_fee
    return render(request, 'orders/checkout.html', {
        'form': form, 'cart': cart, 'items': items,
        'delivery_fee': delivery_fee, 'grand_total': grand_total,
        'ymaps_key': settings.YANDEX_MAPS_KEY,
    })


@login_required
def order_payment_return(request):
    """ЮКасса редиректит сюда после оплаты заказа."""
    order_id = request.GET.get('order_id')
    order = get_object_or_404(Order, id=order_id, user=request.user, status=Order.Status.PAYMENT_PENDING)
    try:
        from yookassa import Configuration, Payment as YKPayment
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
        payment = YKPayment.find_one(order.yookassa_payment_id)
        if payment.status == 'succeeded':
            cart, _ = Cart.objects.get_or_create(user=request.user)
            cart.items.all().delete()
            order.status = Order.Status.PENDING
            order.save(update_fields=['status'])
            _notify_couriers_new_order(order)
            messages.success(request, f'Оплата прошла успешно! Заказ #{order.id} принят.')
            return redirect('orders:order_detail', order_id=order.id)
        else:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            messages.error(request, 'Оплата не прошла. Заказ отменён.')
            return redirect('orders:cart')
    except Exception as e:
        messages.error(request, f'Ошибка проверки платежа: {e}')
        return redirect('orders:cart')



@login_required
def order_list(request):
    if request.user.is_customer:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
    else:
        return redirect('home')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    if request.user.is_customer:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    elif request.user.is_admin_role or request.user.is_staff:
        order = get_object_or_404(Order, id=order_id)
    else:
        return redirect('home')
    items = order.items.all()
    delivery = getattr(order, 'delivery', None)
    ticket = None
    if hasattr(order, 'tickets'):
        ticket = order.tickets.first()
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'items': items,
        'delivery': delivery,
        'ticket': ticket,
    })


@require_POST
@login_required
def suggest_address(request):
    import json, requests as http
    from django.conf import settings
    try:
        body = json.loads(request.body)
        query = body.get('query', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'suggestions': []})
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    try:
        resp = http.post(
            'https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address',
            headers={
                'Authorization': f'Token {settings.DADATA_TOKEN}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json={'query': query, 'count': 6, 'language': 'ru'},
            timeout=3,
        )
        return JsonResponse(resp.json())
    except Exception:
        return JsonResponse({'suggestions': []})


def _notify_couriers_new_order(order):
    import math
    from django.utils import timezone
    from datetime import timedelta
    from apps.accounts.email_utils import send_email

    LOCATION_TTL_HOURS = 4   # позиция считается свежей до 4 часов
    NOTIFY_RADIUS_KM   = 10  # радиус уведомления

    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(float(lat2) - float(lat1))
        dlon = math.radians(float(lon2) - float(lon1))
        a = math.sin(dlat / 2) ** 2 + (
            math.cos(math.radians(float(lat1)))
            * math.cos(math.radians(float(lat2)))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    now = timezone.now()
    fresh_threshold = now - timedelta(hours=LOCATION_TTL_HOURS)

    couriers = User.objects.filter(
        role=User.Role.COURIER, is_active=True
    ).exclude(email_hash='')

    emails = []
    for courier in couriers:
        has_fresh_location = (
            courier.courier_lat is not None
            and courier.courier_lon is not None
            and courier.courier_location_at is not None
            and courier.courier_location_at >= fresh_threshold
        )
        has_order_coords = bool(order.addr_lat and order.addr_lon)

        if has_fresh_location and has_order_coords:
            # Есть свежая геопозиция и адрес заказа — проверяем расстояние
            dist = haversine_km(
                courier.courier_lat, courier.courier_lon,
                order.addr_lat, order.addr_lon,
            )
            if dist <= NOTIFY_RADIUS_KM:
                emails.append((courier.email, round(dist, 1)))
        elif not has_fresh_location:
            # Геопозиция устарела или не установлена — не беспокоим курьера
            pass
        else:
            # Есть свежая геопозиция, но нет координат заказа — уведомляем
            emails.append((courier.email, None))

    if not emails:
        return

    for email, dist_km in emails:
        dist_text = f'{dist_km} км от вас' if dist_km is not None else 'адрес не определён'
        try:
            send_email(
                to=email,
                subject=f'Новый заказ #{order.id} рядом с вами — Доставка МИГ',
                text=(
                    f'Поступил новый заказ #{order.id} в вашем районе!\n\n'
                    f'Адрес доставки: {order.delivery_address}\n'
                    f'Расстояние от вас: {dist_text}\n'
                    f'Сумма заказа: {order.total_price} ₽\n'
                    f'Ваш заработок: {order.delivery_fee} ₽ + 10% от суммы товаров\n\n'
                    f'Войдите в панель курьера, чтобы принять заказ.'
                ),
            )
        except Exception:
            pass
