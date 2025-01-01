
from django.http import JsonResponse
from .models import PriceData
from datetime import datetime

def hello_world(request):
    return JsonResponse({"message": "Hello from Django!"})

def get_prices(request):
    date_str = request.GET.get('date')
    print(f"Received date string: '{date_str}'")  # přidáme quotes abychom viděli přesný string
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        prices = PriceData.objects.filter(date=date)
        
        data = [{
            'hour': price.hour,
            'price_czk': price.price_czk,
            'level': price.level,
            'level_num': price.level_num
        } for price in prices]
        
        return JsonResponse({'prices': data})
    except Exception as e:
        print(f"Error: {type(e).__name__} - {str(e)}")  # detailnější error
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)