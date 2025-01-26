from django.urls import path
from . import views
from . import auth

urlpatterns = [
    path('prices/', views.get_prices, name='get_prices'),
    path('solar_prediction/', views.get_solar_prediction, name='solar_prediction'),
    path('houses/', views.houses, name='houses'),
    path('houses/<int:house_id>/appliances/', views.house_appliances, name='house_appliances'),
    path('auth/verify/', auth.verify_password, name='verify_password'),
    path('auth/check/', auth.check_access, name='check_access'),
    path('houses/<int:house_id>/consumption/', views.consumption_data, name='consumption_data'),
]