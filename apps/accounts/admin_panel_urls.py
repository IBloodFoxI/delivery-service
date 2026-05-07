from django.urls import path
from . import admin_panel_views

app_name = 'admin_panel'

urlpatterns = [
    path('', admin_panel_views.dashboard, name='dashboard'),
    path('users/', admin_panel_views.users_list, name='users_list'),
    path('users/<int:user_id>/role/', admin_panel_views.change_user_role, name='change_user_role'),
    path('orders/', admin_panel_views.orders_list, name='orders_list'),
    path('orders/<int:order_id>/status/', admin_panel_views.change_order_status, name='change_order_status'),
    path('orders/<int:order_id>/cancel/', admin_panel_views.cancel_order, name='cancel_order'),
    path('revenue/', admin_panel_views.revenue, name='revenue'),
    path('revenue/withdrawal/<int:wr_id>/', admin_panel_views.process_withdrawal, name='process_withdrawal'),
    path('tickets/', admin_panel_views.tickets_list, name='tickets_list'),
    path('deliveries/', admin_panel_views.deliveries_list, name='deliveries_list'),
    path('products/', admin_panel_views.products_list, name='products_list'),
    path('products/add/', admin_panel_views.product_add, name='product_add'),
    path('products/<int:product_id>/edit/', admin_panel_views.product_edit, name='product_edit'),
    path('products/<int:product_id>/toggle/', admin_panel_views.product_toggle, name='product_toggle'),
    path('products/<int:product_id>/delete/', admin_panel_views.product_delete, name='product_delete'),
    path('backup/', admin_panel_views.backup_list, name='backup_list'),
    path('backup/create/', admin_panel_views.backup_create, name='backup_create'),
    path('backup/<int:record_id>/download/', admin_panel_views.backup_download, name='backup_download'),
    path('backup/<int:record_id>/restore/', admin_panel_views.backup_restore, name='backup_restore'),
    path('backup/<int:record_id>/delete/', admin_panel_views.backup_delete, name='backup_delete'),
    path('backup/settings/', admin_panel_views.backup_settings, name='backup_settings'),
    path('export/pdf/', admin_panel_views.export_pdf, name='export_pdf'),
    path('backup/sql/create/', admin_panel_views.backup_sql_create, name='backup_sql_create'),
    path('backup/sql/<int:record_id>/restore/', admin_panel_views.backup_sql_restore, name='backup_sql_restore'),
]
