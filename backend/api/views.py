from django.http import JsonResponse
from .models import PriceData, SolarData
from datetime import datetime
import logging

logger = logging.getLogger('api')

def get_prices(request):
   date_str = request.GET.get('date')
   logger.info(f"Received get_prices request for {date_str}")
   
   try:
       # Převod datumu z formátu YYYY-MM-DD
       date = datetime.strptime(date_str, '%Y-%m-%d').date()
       logger.debug(f"Successfully parsed date {date}")
       
       # Získání dat pro daný den
       prices = PriceData.objects.filter(date=date)
       
       # Kontrola jestli existují data
       if not prices.exists():
           logger.warning(f"No price data found for date {date}")
           return JsonResponse(
               {'error': 'No data available for this date'}, 
               status=404
           )
       
       # Příprava dat pro JSON
       data = [{
           'hour': price.hour,
           'price_czk': price.price_czk,
           'level': price.level,
           'level_num': price.level_num
       } for price in prices]
       
       logger.info(f"Successfully returned {len(data)} price records for {date}")
       return JsonResponse({'prices': data})
       
   except ValueError as e:
       # Chyba při parsování data
       logger.error(f"Invalid date format: {date_str}")
       return JsonResponse(
           {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
           status=400
       )
   except Exception as e:
       # Neočekávané chyby
       logger.error(f"Unexpected error when getting prices for {date_str}: {str(e)}")
       return JsonResponse(
           {'error': 'Internal server error'}, 
           status=500
       )
    
def get_solar_prediction(request):
   date_str = request.GET.get('date')
   logger.info(f"Received get_solar_prediction request for {date_str}")
   
   try:
       # Převod datumu z formátu YYYY-MM-DD
       date = datetime.strptime(date_str, '%Y-%m-%d').date()
       logger.debug(f"Successfully parsed date {date}")
       
       # Získání dat pro daný den
       solar_data = SolarData.objects.filter(
           timestamp__date=date
       ).order_by('timestamp')
       
       # Kontrola jestli existují data
       if not solar_data.exists():
           logger.warning(f"No solar data found for date {date}")
           return JsonResponse(
               {'error': 'No data available for this date'}, 
               status=404
           )
       
       # Příprava dat pro JSON
       data = [{
           'timestamp': solar.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
           'watts': solar.watts,
           'watt_hours_period': solar.watt_hours_period,
           'watt_hours_cumulative': solar.watt_hours_cumulative,
           'hour': solar.timestamp.hour  # Přidáno pro kompatibilitu s frontend
       } for solar in solar_data]
       
       # Přidání denního součtu
       daily_total = solar_data.last().watt_hours_cumulative if solar_data.exists() else 0
       
       response = {
           'predictions': data,
           'daily_total': daily_total
       }
       
       logger.info(f"Successfully returned {len(data)} solar predictions for {date} with daily total {daily_total}Wh")
       return JsonResponse(response)
       
   except ValueError as e:
       # Chyba při parsování data
       logger.error(f"Invalid date format: {date_str}")
       return JsonResponse({
           'error': 'Invalid date format. Use YYYY-MM-DD',
           'detail': str(e)
       }, status=400)
   except Exception as e:
       # Neočekávané chyby
       logger.error(f"Unexpected error when getting solar predictions for {date_str}: {str(e)}")
       return JsonResponse({
           'error': 'Internal server error',
           'detail': str(e)
       }, status=500)