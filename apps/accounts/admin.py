from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, BalanceTransaction


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['phone_number', 'full_name', 'role', 'balance', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['phone_number', 'full_name']
    ordering = ['-date_joined']
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Личные данные', {'fields': ('full_name', 'avatar')}),
        ('Роль и баланс', {'fields': ('role', 'balance')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'transaction_type', 'created_at']
    list_filter = ['transaction_type']
    search_fields = ['user__phone_number', 'user__full_name']
    readonly_fields = ['created_at']
