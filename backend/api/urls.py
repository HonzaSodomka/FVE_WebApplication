from django.urls import path
from . import views

urlpatterns = [
    path('prices/', views.get_prices, name='get_prices'),
    path('solar_prediction/', views.get_solar_prediction, name='solar_prediction'),
]