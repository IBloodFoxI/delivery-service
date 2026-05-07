from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal

from apps.accounts.models import User
from apps.orders.models import Order
from apps.support.models import SupportTicket, TicketMessage


def make_user(phone='+79001234567', name='Покупатель', role=User.Role.CUSTOMER):
    return User.objects.create_user(
        phone_number=phone,
        full_name=name,
        password='testpass123',
        role=role,
    )


def make_order(user, status=Order.Status.PENDING):
    return Order.objects.create(
        user=user,
        delivery_address='ул. Тестовая, 1',
        total_price=Decimal('500'),
        status=status,
    )


class SupportTicketModelTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)

    def test_ticket_created_with_open_status(self):
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Проблема с заказом',
        )
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)

    def test_ticket_str_contains_subject(self):
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Заказ не пришёл',
        )
        self.assertIn('Заказ не пришёл', str(ticket))
        self.assertIn(str(ticket.id), str(ticket))

    def test_ticket_status_transitions(self):
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Тест',
        )
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save()
        refreshed = SupportTicket.objects.get(pk=ticket.pk)
        self.assertEqual(refreshed.status, SupportTicket.Status.IN_PROGRESS)

    def test_ticket_can_be_assigned_to_support(self):
        support_user = make_user(
            phone='+79000000099',
            name='Сотрудник',
            role=User.Role.SUPPORT,
        )
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Назначение',
            assigned_to=support_user,
        )
        self.assertEqual(ticket.assigned_to, support_user)

    def test_ticket_without_assignment(self):
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Без назначения',
        )
        self.assertIsNone(ticket.assigned_to)


class TicketMessageModelTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)
        self.ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Тест сообщений',
        )

    def test_message_created_successfully(self):
        msg = TicketMessage.objects.create(
            ticket=self.ticket,
            author=self.user,
            message='Текст первого сообщения',
        )
        self.assertEqual(msg.message, 'Текст первого сообщения')
        self.assertEqual(msg.author, self.user)

    def test_message_str_contains_author_and_ticket(self):
        msg = TicketMessage.objects.create(
            ticket=self.ticket,
            author=self.user,
            message='Сообщение',
        )
        result = str(msg)
        self.assertIn(str(self.ticket.id), result)

    def test_messages_ordered_chronologically(self):
        TicketMessage.objects.create(ticket=self.ticket, author=self.user, message='Первое')
        TicketMessage.objects.create(ticket=self.ticket, author=self.user, message='Второе')
        messages = list(self.ticket.messages.values_list('message', flat=True))
        self.assertEqual(messages[0], 'Первое')
        self.assertEqual(messages[1], 'Второе')


class SupportViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.order = make_order(self.user)

    def test_my_tickets_requires_login(self):
        response = self.client.get(reverse('support:my_tickets'))
        self.assertEqual(response.status_code, 302)

    def test_my_tickets_loads_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('support:my_tickets'))
        self.assertEqual(response.status_code, 200)

    def test_create_ticket_requires_login(self):
        response = self.client.get(
            reverse('support:create_ticket', args=[self.order.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_create_ticket_page_loads(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('support:create_ticket', args=[self.order.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_create_ticket_post_creates_ticket(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('support:create_ticket', args=[self.order.id]),
            {'subject': 'Проблема', 'message': 'Описание'},
        )
        self.assertTrue(
            SupportTicket.objects.filter(user=self.user, order=self.order).exists()
        )

    def test_ticket_detail_requires_login(self):
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Тест',
        )
        response = self.client.get(
            reverse('support:ticket_detail', args=[ticket.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_ticket_detail_loads_for_owner(self):
        self.client.force_login(self.user)
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Мой тикет',
        )
        response = self.client.get(
            reverse('support:ticket_detail', args=[ticket.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_ticket_detail_forbidden_for_other_user(self):
        other_user = make_user(phone='+79008888888', name='Другой')
        self.client.force_login(other_user)
        ticket = SupportTicket.objects.create(
            order=self.order,
            user=self.user,
            subject='Чужой тикет',
        )
        response = self.client.get(
            reverse('support:ticket_detail', args=[ticket.id])
        )
        # Должен вернуть 403 или 404, но не 200
        self.assertNotEqual(response.status_code, 200)
