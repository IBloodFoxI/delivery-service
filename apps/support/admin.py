from django.contrib import admin
from .models import SupportTicket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ['author', 'message', 'created_at']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'user', 'order', 'status', 'assigned_to', 'created_at']
    list_filter = ['status']
    search_fields = ['subject', 'user__full_name']
    inlines = [TicketMessageInline]
