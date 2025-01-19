from django.urls import path
from . import views

urlpatterns = [
    path('prices/', views.get_prices, name='get_prices'),
    path('solar_prediction/', views.get_solar_prediction, name='solar_prediction'),
    path('houses/', views.houses, name='houses'),
    path('houses/<int:house_id>/appliances/', views.house_appliances, name='house_appliances'),
    path('verify_password/', views.verify_password, name='verify_password'),
]