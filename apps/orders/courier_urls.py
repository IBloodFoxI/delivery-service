from django.urls import path
from . import courier_views

app_name = 'courier'

urlpatterns = [
    path('', courier_views.dashboard, name='dashboard'),
    path('accept/<int:order_id>/', courier_views.accept_order, name='accept_order'),
    path('start/<int:order_id>/', courier_views.start_delivery, name='start_delivery'),
    path('complete/<int:order_id>/', courier_views.complete_delivery, name='complete_delivery'),
    path('order/<int:order_id>/', courier_views.order_detail, name='order_detail'),
    path('location/update/', courier_views.update_location, name='update_location'),
    path('wallet/', courier_views.wallet, name='wallet'),
    path('wallet/withdraw/', courier_views.request_withdrawal, name='request_withdrawal'),
]
