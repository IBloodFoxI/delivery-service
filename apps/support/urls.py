from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('ticket/new/<int:order_id>/', views.create_ticket, name='create_ticket'),
    path('ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('my-tickets/', views.my_tickets, name='my_tickets'),
]
