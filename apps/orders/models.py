from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.catalog.models import Product


class PromoCode(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Процент (%)'
        FIXED = 'fixed', 'Фиксированная сумма (₽)'

    code = models.CharField(max_length=50, unique=True, verbose_name='Промокод')
    description = models.CharField(max_length=255, blank=True, verbose_name='Описание')
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, verbose_name='Тип скидки')
    discount_value = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Размер скидки')

    # Условия применения
    min_cart_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Мин. сумма корзины (₽)'
    )
    first_order_only = models.BooleanField(default=False, verbose_name='Только первый заказ')
    category_condition = models.ForeignKey(
        'catalog.Category', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Только для категории'
    )
    product_condition = models.ForeignKey(
        'catalog.Product', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', verbose_name='Только для товара'
    )

    usage_limit = models.PositiveIntegerField(default=0, verbose_name='Лимит использований (0 = ∞)')
    times_used = models.PositiveIntegerField(default=0, verbose_name='Использован раз')

    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='Действует с')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='Действует до')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def validate(self, cart, user):
        """Проверяет промокод. Возвращает (discount_amount, error_str)."""
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return Decimal('0'), 'Промокод ещё не активен'
        if self.valid_until and now > self.valid_until:
            return Decimal('0'), 'Срок действия промокода истёк'
        if self.usage_limit > 0 and self.times_used >= self.usage_limit:
            return Decimal('0'), 'Промокод исчерпан'

        cart_items = list(cart.items.select_related('product__category').all())
        cart_total = sum(i.subtotal for i in cart_items)

        if self.min_cart_amount and cart_total < self.min_cart_amount:
            return Decimal('0'), f'Минимальная сумма для промокода: {self.min_cart_amount} ₽'

        if self.first_order_only:
            from apps.orders.models import Order
            if user.orders.filter(status=Order.Status.DELIVERED).exists():
                return Decimal('0'), 'Промокод действует только на первый заказ'

        # Определяем базу для расчёта скидки
        if self.product_condition_id:
            base = sum(i.subtotal for i in cart_items if i.product_id == self.product_condition_id)
            if not base:
                return Decimal('0'), f'Промокод действует только на «{self.product_condition.name}»'
        elif self.category_condition_id:
            base = sum(i.subtotal for i in cart_items if i.product.category_id == self.category_condition_id)
            if not base:
                return Decimal('0'), f'Промокод действует только на категорию «{self.category_condition.name}»'
        else:
            base = cart_total

        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (base * self.discount_value / 100).quantize(Decimal('0.01'))
        else:
            discount = min(self.discount_value, base)

        return discount, None


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f'Корзина {self.user}'

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ['cart', 'product']

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'


DELIVERY_FEE = 100  # фиксированная стоимость доставки


class Order(models.Model):
    class Status(models.TextChoices):
        PAYMENT_PENDING = 'payment_pending', 'Ожидает оплаты'
        PENDING = 'pending', 'Ожидает курьера'
        ASSIGNED = 'assigned', 'Курьер назначен'
        IN_PROGRESS = 'in_progress', 'В пути'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменён'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='orders', verbose_name='Покупатель'
    )
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='courier_orders', verbose_name='Курьер'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    delivery_address = models.CharField(max_length=500, verbose_name='Адрес доставки')
    addr_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Широта')
    addr_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Долгота')
    comment = models.TextField(blank=True, verbose_name='Комментарий курьеру')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Итого')
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=100, verbose_name='Стоимость доставки')
    yookassa_payment_id = models.CharField(max_length=100, blank=True, default='', verbose_name='ID платежа ЮКасса')
    promo_code = models.ForeignKey(
        PromoCode, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name='Промокод', related_name='orders'
    )
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='Скидка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлён')

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ #{self.id} от {self.user}'

    @property
    def cart_total(self):
        """Сумма товаров без доставки."""
        return self.total_price - self.delivery_fee

    @property
    def status_badge_class(self):
        mapping = {
            'payment_pending': 'secondary',
            'pending': 'warning',
            'assigned': 'info',
            'in_progress': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
        }
        return mapping.get(self.status, 'secondary')


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    @property
    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'


class Delivery(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='deliveries', verbose_name='Курьер'
    )
    # Заглушка для мобильного приложения — будет использоваться позже
    estimated_minutes = models.PositiveIntegerField(default=30, verbose_name='Примерное время (мин)')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начало доставки')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершено')
    courier_location_stub = models.CharField(
        max_length=100, blank=True,
        verbose_name='Координаты курьера (заглушка)',
        help_text='Будет использоваться мобильным приложением'
    )

    class Meta:
        verbose_name = 'Доставка'
        verbose_name_plural = 'Доставки'

    def __str__(self):
        return f'Доставка заказа #{self.order_id}'
