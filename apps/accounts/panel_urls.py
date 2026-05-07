from django.urls import path, include

urlpatterns = [
    path('admin/', include('apps.accounts.admin_panel_urls')),
    path('courier/', include('apps.orders.courier_urls')),
    path('support/', include('apps.support.panel_urls')),
]
