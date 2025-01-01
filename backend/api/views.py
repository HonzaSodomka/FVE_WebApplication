
from django.http import JsonResponse
from .models import PriceData
from datetime import datetime

def hello_world(request):
    return JsonResponse({"message": "Hello from Django!"})

def get_prices(request):
    date_str = request.GET.get('date')
    
    try:
        # Převod datumu z formátu YYYY-MM-DD
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Získání dat pro daný den
        prices = PriceData.objects.filter(date=date)
        
        # Příprava dat pro JSON
        data = [{
            'hour': price.hour,
            'price_czk': price.price_czk,
            'level': price.level,
            'level_num': price.level_num
        } for price in prices]
        
        return JsonResponse({'prices': data})
    except:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)