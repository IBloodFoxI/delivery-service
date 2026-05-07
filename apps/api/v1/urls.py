from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register('categories', views.CategoryViewSet, basename='categories')
router.register('products', views.ProductViewSet, basename='products')
router.register('orders', views.OrderViewSet, basename='orders')
router.register('tickets', views.SupportTicketViewSet, basename='tickets')

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='api-register'),
    path('auth/login/', views.LoginView.as_view(), name='api-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='api-token-refresh'),
    path('profile/', views.ProfileView.as_view(), name='api-profile'),
    path('profile/topup/', views.BalanceTopUpView.as_view(), name='api-topup'),
    path('cart/', views.CartView.as_view(), name='api-cart'),
    path('', include(router.urls)),
]
