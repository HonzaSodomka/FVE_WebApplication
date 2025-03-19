"""
Konfigurace URL tras pro FVE API.

Tento modul definuje všechny dostupné API endpointy aplikace, včetně:
- Endpointů pro cenová data a solární predikce
- Správy domů a jejich spotřebičů
- Autentizace a kontroly přístupu
- Dat o spotřebě a nabíjení
- Plánů nabíjení
"""

from django.urls import path
from . import views
from . import auth


urlpatterns = [
    # Endpointy pro cenová data a predikce
    path('prices/', views.get_prices, name='get_prices'),
    path('solar_prediction/', views.get_solar_prediction, name='solar_prediction'),
    
    # Správa domů a spotřebičů
    path('houses/', views.houses, name='houses'),
    path('houses/<int:house_id>/appliances/', views.house_appliances, name='house_appliances'),
    
    # Autentizace a kontrola přístupu
    path('auth/verify/', auth.verify_password, name='verify_password'),
    path('auth/check/', auth.check_access, name='check_access'),
    
    # Data o spotřebě a nabíjení
    path('houses/<int:house_id>/consumption/', views.consumption_data, name='consumption_data'),
    path('houses/<int:house_id>/charging/', views.charging_data, name='charging_data'),
    
    # Simulace a plány nabíjení
    path('houses/<int:house_id>/toggle_simulation/', views.toggle_simulation, name='toggle_simulation'),
    path('houses/<int:house_id>/charging_schedule/', views.charging_schedule, name='charging_schedule'),
]