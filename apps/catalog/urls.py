from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('favorite/<int:product_id>/toggle/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/', views.favorites_list, name='favorites'),
]
