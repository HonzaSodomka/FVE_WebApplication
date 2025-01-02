
from django.http import JsonResponse
from .models import PriceData, SolarData
from datetime import datetime

def hello_world(request):
    return JsonResponse({"message": "Hello from Django!"})

import logging
logger = logging.getLogger(__name__)

def get_prices(request):
    date_str = request.GET.get('date')
    logger.info(f"Received date string: '{date_str}'")
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        logger.info(f"Parsed date: {date}")
        
        prices = PriceData.objects.filter(date=date)
        logger.info(f"Found prices: {prices.count()}")
        
        data = [{
            'hour': price.hour,
            'price_czk': price.price_czk,
            'level': price.level,
            'level_num': price.level_num
        } for price in prices]
        
        return JsonResponse({'prices': data})
    except Exception as e:
        logger.error(f"Error: {type(e).__name__} - {str(e)}")
        return JsonResponse({'error': f'Invalid date format. Use YYYY-MM-DD. Error: {str(e)}'}, status=400)
    
def get_solar_prediction(request):
    date_str = request.GET.get('date')
    
    try:
        # Převod datumu z formátu YYYY-MM-DD
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Získání dat pro daný den
        solar_data = SolarData.objects.filter(
            timestamp__date=date
        ).order_by('timestamp')
        
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
        
        return JsonResponse(response)
        
    except Exception as e:
        return JsonResponse({
            'error': 'Invalid date format. Use YYYY-MM-DD',
            'detail': str(e)
        }, status=400)