from django.test import TestCase, Client
from django.urls import reverse
from apps.catalog.models import Category, Product
from decimal import Decimal


class CategoryModelTest(TestCase):

    def test_category_created_with_auto_slug(self):
        category = Category.objects.create(name='Суши', order=1)
        self.assertEqual(category.name, 'Суши')
        self.assertNotEqual(category.slug, '')
        self.assertIsNotNone(category.slug)

    def test_slug_not_overwritten_if_set(self):
        category = Category.objects.create(name='Пицца', slug='pizza', order=0)
        self.assertEqual(category.slug, 'pizza')

    def test_category_ordering_by_order_field(self):
        Category.objects.create(name='Б', order=2)
        Category.objects.create(name='А', order=1)
        names = list(Category.objects.values_list('name', flat=True))
        self.assertEqual(names[0], 'А')

    def test_str_representation(self):
        category = Category.objects.create(name='Роллы', order=0)
        self.assertEqual(str(category), 'Роллы')


class ProductModelTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(name='Тест', order=0)

    def _make_product(self, **kwargs):
        defaults = {
            'category': self.category,
            'name': 'Тестовый продукт',
            'price': Decimal('150.00'),
            'weight': 200,
            'calories': Decimal('200.0'),
            'proteins': Decimal('10.0'),
            'fats': Decimal('8.0'),
            'carbs': Decimal('25.0'),
            'is_available': True,
        }
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    def test_product_created_successfully(self):
        product = self._make_product()
        self.assertEqual(product.name, 'Тестовый продукт')
        self.assertEqual(product.price, Decimal('150.00'))
        self.assertTrue(product.is_available)

    def test_kbju_calculation_correct(self):
        # weight=200г → factor=2
        product = self._make_product(
            weight=200,
            calories=Decimal('200.0'),
            proteins=Decimal('10.0'),
            fats=Decimal('8.0'),
            carbs=Decimal('25.0'),
        )
        kbju = product.kbju_per_product
        self.assertIsNotNone(kbju)
        self.assertAlmostEqual(kbju['calories'], 400.0, places=1)
        self.assertAlmostEqual(kbju['proteins'], 20.0, places=1)
        self.assertAlmostEqual(kbju['fats'], 16.0, places=1)
        self.assertAlmostEqual(kbju['carbs'], 50.0, places=1)

    def test_kbju_returns_none_for_zero_weight(self):
        product = self._make_product(weight=0)
        self.assertIsNone(product.kbju_per_product)

    def test_str_representation(self):
        product = self._make_product(name='Ролл Филадельфия')
        self.assertEqual(str(product), 'Ролл Филадельфия')

    def test_unavailable_product_flag(self):
        product = self._make_product(is_available=False)
        self.assertFalse(product.is_available)

    def test_kbju_100g_product(self):
        product = self._make_product(
            weight=100,
            calories=Decimal('300.0'),
            proteins=Decimal('15.0'),
        )
        kbju = product.kbju_per_product
        # factor=1, значения равны исходным
        self.assertAlmostEqual(kbju['calories'], 300.0, places=1)
        self.assertAlmostEqual(kbju['proteins'], 15.0, places=1)


class CatalogViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Тест', order=0)
        self.product = Product.objects.create(
            category=self.category,
            name='Видимый продукт',
            price=Decimal('200.00'),
            weight=300,
            is_available=True,
        )

    def test_catalog_page_loads(self):
        response = self.client.get(reverse('catalog:product_list'))
        self.assertEqual(response.status_code, 200)

    def test_catalog_shows_available_products(self):
        response = self.client.get(reverse('catalog:product_list'))
        self.assertContains(response, 'Видимый продукт')

    def test_product_detail_page_loads(self):
        response = self.client.get(
            reverse('catalog:product_detail', args=[self.product.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_product_detail_404_for_missing(self):
        response = self.client.get(
            reverse('catalog:product_detail', args=[99999])
        )
        self.assertEqual(response.status_code, 404)
