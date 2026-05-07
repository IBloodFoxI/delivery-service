from django.db import models
from django.conf import settings
from apps.orders.models import Order


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Открыт'
        IN_PROGRESS = 'in_progress', 'В обработке'
        CLOSED = 'closed', 'Закрыт'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets', verbose_name='Заказ')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='support_tickets', verbose_name='Автор'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_tickets', verbose_name='Назначен сотруднику'
    )
    subject = models.CharField(max_length=255, verbose_name='Тема')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Тикет'
        verbose_name_plural = 'Тикеты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Тикет #{self.id}: {self.subject}'


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Автор')
    message = models.TextField(verbose_name='Сообщение')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение в тикете'
        verbose_name_plural = 'Сообщения в тикетах'

    def __str__(self):
        return f'Сообщение от {self.author} в тикете #{self.ticket_id}'
