from django.urls import path
from . import panel_views

app_name = 'support_panel'

urlpatterns = [
    path('', panel_views.dashboard, name='dashboard'),
    path('ticket/<int:ticket_id>/', panel_views.ticket_detail, name='ticket_detail'),
    path('ticket/<int:ticket_id>/close/', panel_views.close_ticket, name='close_ticket'),
    path('deliveries/', panel_views.deliveries_list, name='deliveries_list'),
    path('deliveries/<int:order_id>/cancel/', panel_views.cancel_delivery, name='cancel_delivery'),
    path('export/pdf/', panel_views.export_pdf, name='export_pdf'),
]
