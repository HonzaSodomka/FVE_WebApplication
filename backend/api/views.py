
from django.http import JsonResponse
from .models import PriceData
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