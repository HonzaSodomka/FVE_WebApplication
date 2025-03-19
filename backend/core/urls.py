"""
URL konfigurace pro FVE aplikaci.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Administrační rozhraní
    path('admin/', admin.site.urls),
    # API endpointy
    path('api/', include('api.urls')),
]