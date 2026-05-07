from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, BalanceTransaction
from decimal import Decimal


class UserModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+79001234567',
            full_name='Иван Иванов',
            password='testpass123',
            role=User.Role.CUSTOMER,
        )

    def test_user_created_successfully(self):
        self.assertEqual(self.user.phone_number, '+79001234567')
        self.assertEqual(self.user.full_name, 'Иван Иванов')
        self.assertTrue(self.user.is_active)

    def test_customer_role_properties(self):
        self.assertTrue(self.user.is_customer)
        self.assertFalse(self.user.is_courier)
        self.assertFalse(self.user.is_support)
        self.assertFalse(self.user.is_admin_role)

    def test_courier_role_properties(self):
        courier = User.objects.create_user(
            phone_number='+79007654321',
            full_name='Курьер Тест',
            password='testpass123',
            role=User.Role.COURIER,
        )
        self.assertTrue(courier.is_courier)
        self.assertFalse(courier.is_customer)

    def test_support_role_properties(self):
        support = User.objects.create_user(
            phone_number='+79000000001',
            full_name='Сотрудник Поддержки',
            password='testpass123',
            role=User.Role.SUPPORT,
        )
        self.assertTrue(support.is_support)
        self.assertFalse(support.is_customer)

    def test_admin_role_properties(self):
        admin = User.objects.create_user(
            phone_number='+79000000002',
            full_name='Администратор',
            password='testpass123',
            role=User.Role.ADMIN,
        )
        self.assertTrue(admin.is_admin_role)
        self.assertFalse(admin.is_customer)

    def test_str_representation(self):
        result = str(self.user)
        self.assertIn('Иван Иванов', result)
        self.assertIn('+79001234567', result)

    def test_initial_balance_is_zero(self):
        self.assertEqual(self.user.balance, Decimal('0'))

    def test_phone_number_is_unique(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                phone_number='+79001234567',
                full_name='Дубликат',
                password='testpass123',
            )


class RegisterViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:register')

    def test_register_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_register_valid_user(self):
        self.client.post(self.url, {
            'phone_number': '+79001111111',
            'full_name': 'Новый Пользователь',
            'password1': 'strongP@ss999',
            'password2': 'strongP@ss999',
        })
        self.assertTrue(User.objects.filter(phone_number='+79001111111').exists())

    def test_register_duplicate_phone_rejected(self):
        User.objects.create_user(
            phone_number='+79001111111',
            full_name='Существующий',
            password='testpass123',
        )
        self.client.post(self.url, {
            'phone_number': '+79001111111',
            'full_name': 'Дубликат',
            'password1': 'strongP@ss999',
            'password2': 'strongP@ss999',
        })
        self.assertEqual(User.objects.filter(phone_number='+79001111111').count(), 1)

    def test_register_passwords_mismatch_rejected(self):
        self.client.post(self.url, {
            'phone_number': '+79001234999',
            'full_name': 'Тест',
            'password1': 'strongP@ss999',
            'password2': 'differentpass',
        })
        self.assertFalse(User.objects.filter(phone_number='+79001234999').exists())

    def test_authenticated_user_redirected_from_register(self):
        user = User.objects.create_user(
            phone_number='+79002222222',
            full_name='Залогиненный',
            password='testpass123',
        )
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


class LoginViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:login')
        self.user = User.objects.create_user(
            phone_number='+79001234567',
            full_name='Тест Юзер',
            password='testpass123',
        )

    def test_login_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_login_valid_credentials_redirects(self):
        response = self.client.post(self.url, {
            'phone_number': '+79001234567',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_password_stays_on_page(self):
        response = self.client.post(self.url, {
            'phone_number': '+79001234567',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_nonexistent_user_stays_on_page(self):
        response = self.client.post(self.url, {
            'phone_number': '+79009999999',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


class ProfileViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone_number='+79001234567',
            full_name='Тест Юзер',
            password='testpass123',
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)

    def test_profile_accessible_when_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

    def test_profile_contains_user_name(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:profile'))
        self.assertContains(response, 'Тест Юзер')


class BalanceTransactionTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+79001234567',
            full_name='Тест Юзер',
            password='testpass123',
        )

    def test_balance_transaction_str(self):
        tx = BalanceTransaction.objects.create(
            user=self.user,
            amount=Decimal('500.00'),
            transaction_type=BalanceTransaction.TransactionType.TOPUP,
            description='Тестовое пополнение',
        )
        result = str(tx)
        self.assertIn('500', result)

    def test_topup_view_requires_login(self):
        client = Client()
        response = client.get(reverse('accounts:topup'))
        self.assertEqual(response.status_code, 302)
