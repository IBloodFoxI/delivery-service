from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, Order, OrderItem, PromoCode


def make_user(phone='+79001234567', name='Покупатель', role=User.Role.CUSTOMER):
    return User.objects.create_user(
        phone_number=phone,
        full_name=name,
        password='testpass123',
        role=role,
    )


def make_category(name='Тест'):
    return Category.objects.create(name=name, order=0)


def make_product(category, name='Продукт', price='500.00', weight=300):
    return Product.objects.create(
        category=category,
        name=name,
        price=Decimal(price),
        weight=weight,
        is_available=True,
    )

class CartModelTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.category = make_category()
        self.product = make_product(self.category)
        self.cart = Cart.objects.create(user=self.user)

    def test_empty_cart_total_price_is_zero(self):
        self.assertEqual(self.cart.total_price, 0)

    def test_empty_cart_total_items_is_zero(self):
        self.assertEqual(self.cart.total_items, 0)

    def test_cart_total_price_with_items(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=3)
        # 3 × 500 = 1500
        self.assertEqual(self.cart.total_price, Decimal('1500.00'))

    def test_cart_total_items_count(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.assertEqual(self.cart.total_items, 2)

    def test_cart_str_contains_user(self):
        self.assertIn('Покупатель', str(self.cart))


class CartItemTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.category = make_category()
        self.product = make_product(self.category, price='200.00')
        self.cart = Cart.objects.create(user=self.user)

    def test_cartitem_subtotal(self):
        item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=4)
        self.assertEqual(item.subtotal, Decimal('800.00'))

    def test_cartitem_str(self):
        item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.assertIn('Продукт', str(item))
        self.assertIn('2', str(item))


class PromoCodeValidationTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.category = make_category()
        self.product = make_product(self.category, price='500.00')
        self.cart = Cart.objects.create(user=self.user)
        # 2 × 500 = 1000 ₽ в корзине
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)

    def _promo(self, **kwargs):
        defaults = {
            'code': 'TEST10',
            'discount_type': PromoCode.DiscountType.PERCENTAGE,
            'discount_value': Decimal('10'),
            'is_active': True,
        }
        defaults.update(kwargs)
        return PromoCode.objects.create(**defaults)

    # --- Успешные случаи ---

    def test_percentage_discount_applied_correctly(self):
        promo = self._promo()
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)
        # 10% от 1000 = 100
        self.assertEqual(discount, Decimal('100.00'))

    def test_fixed_discount_applied_correctly(self):
        promo = self._promo(
            code='FIXED50',
            discount_type=PromoCode.DiscountType.FIXED,
            discount_value=Decimal('50'),
        )
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)
        self.assertEqual(discount, Decimal('50'))

    def test_fixed_discount_capped_by_cart_total(self):
        # Скидка больше суммы корзины — должна быть ограничена суммой корзины
        promo = self._promo(
            code='HUGE',
            discount_type=PromoCode.DiscountType.FIXED,
            discount_value=Decimal('9999'),
        )
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)
        self.assertEqual(discount, Decimal('1000.00'))

    def test_first_order_promo_valid_for_new_user(self):
        promo = self._promo(first_order_only=True)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)

    def test_min_cart_amount_satisfied(self):
        promo = self._promo(min_cart_amount=Decimal('500'))
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)

    def test_product_condition_satisfied(self):
        promo = self._promo(product_condition=self.product)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)
        # Скидка только на этот товар: 10% от 1000 = 100
        self.assertEqual(discount, Decimal('100.00'))

    def test_category_condition_satisfied(self):
        promo = self._promo(category_condition=self.category)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)

    # --- Ошибочные случаи ---

    def test_expired_promo_rejected(self):
        promo = self._promo(valid_until=timezone.now() - timedelta(days=1))
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertIn('истёк', error)
        self.assertEqual(discount, Decimal('0'))

    def test_not_yet_active_promo_rejected(self):
        promo = self._promo(valid_from=timezone.now() + timedelta(days=1))
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertIn('не активен', error)

    def test_usage_limit_exceeded_rejected(self):
        promo = self._promo(usage_limit=5, times_used=5)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertIn('исчерпан', error)

    def test_min_cart_amount_not_met_rejected(self):
        promo = self._promo(min_cart_amount=Decimal('2000'))
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertEqual(discount, Decimal('0'))

    def test_first_order_promo_rejected_for_existing_customer(self):
        # Создаём уже доставленный заказ
        Order.objects.create(
            user=self.user,
            delivery_address='ул. Тестовая, 1',
            total_price=Decimal('500'),
            status=Order.Status.DELIVERED,
        )
        promo = self._promo(first_order_only=True)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertIn('первый', error)

    def test_category_condition_not_met_rejected(self):
        other_category = Category.objects.create(name='Другая категория', order=1)
        promo = self._promo(category_condition=other_category)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertEqual(discount, Decimal('0'))

    def test_product_condition_not_met_rejected(self):
        other_product = make_product(self.category, name='Другой продукт', price='100.00')
        promo = self._promo(product_condition=other_product)
        # В корзине нет other_product
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNotNone(error)
        self.assertEqual(discount, Decimal('0'))

    def test_unlimited_usage_promo_never_exhausted(self):
        # usage_limit=0 означает бесконечный лимит
        promo = self._promo(usage_limit=0, times_used=9999)
        discount, error = promo.validate(self.cart, self.user)
        self.assertIsNone(error)




class OrderModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_order_default_status_is_pending(self):
        order = Order.objects.create(
            user=self.user,
            delivery_address='ул. Тестовая, 1',
            total_price=Decimal('500'),
        )
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_order_str_contains_id(self):
        order = Order.objects.create(
            user=self.user,
            delivery_address='ул. Тестовая, 1',
            total_price=Decimal('500'),
        )
        self.assertIn(str(order.id), str(order))

    def test_status_badge_classes_mapping(self):
        order = Order(
            user=self.user,
            delivery_address='Тест',
            total_price=Decimal('0'),
        )
        cases = [
            (Order.Status.PENDING, 'warning'),
            (Order.Status.ASSIGNED, 'info'),
            (Order.Status.IN_PROGRESS, 'primary'),
            (Order.Status.DELIVERED, 'success'),
            (Order.Status.CANCELLED, 'danger'),
        ]
        for status, expected_class in cases:
            order.status = status
            self.assertEqual(order.status_badge_class, expected_class)


class OrderItemTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.category = make_category()
        self.product = make_product(self.category, price='250.00')
        self.order = Order.objects.create(
            user=self.user,
            delivery_address='Тест',
            total_price=Decimal('500'),
        )

    def test_orderitem_subtotal(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Продукт',
            quantity=3,
            price=Decimal('250.00'),
        )
        self.assertEqual(item.subtotal, Decimal('750.00'))

    def test_orderitem_str(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Ролл',
            quantity=2,
            price=Decimal('200.00'),
        )
        self.assertIn('Ролл', str(item))




class CartViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.category = make_category()
        self.product = make_product(self.category)

    def test_cart_page_requires_login(self):
        response = self.client.get(reverse('orders:cart'))
        self.assertEqual(response.status_code, 302)

    def test_cart_page_loads_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('orders:cart'))
        self.assertEqual(response.status_code, 200)

    def test_add_to_cart_requires_login(self):
        response = self.client.post(
            reverse('orders:add_to_cart', args=[self.product.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_add_to_cart_creates_cart_and_item(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('orders:add_to_cart', args=[self.product.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertTrue(Cart.objects.filter(user=self.user).exists())
        cart = Cart.objects.get(user=self.user)
        self.assertTrue(cart.items.filter(product=self.product).exists())

    def test_checkout_requires_login(self):
        response = self.client.get(reverse('orders:checkout'))
        self.assertEqual(response.status_code, 302)

    def test_order_list_requires_login(self):
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, 302)

    def test_order_list_loads_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, 200)
