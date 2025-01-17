from django.http import JsonResponse
from .models import PriceData, SolarData, House
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
import json


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
   
@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE", "PATCH"])
def houses(request):
    if request.method == "GET":
        try:
            houses_list = list(House.objects.values())
            return JsonResponse({'houses': houses_list})
        except Exception as e:
            logger.error(f"Error fetching houses: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            house = House.objects.create(
                name=data['name'],
                solar_power=data['solar_power'],
                battery_capacity=data['battery_capacity']
            )
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity
            }, status=201)
        except KeyError as e:
            return JsonResponse({'error': f'Chybějící pole: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error creating house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "DELETE":
        try:
            house_id = request.GET.get('id')
            if not house_id:
                return JsonResponse({'error': 'Chybí ID domu'}, status=400)
                
            house = House.objects.get(id=house_id)
            house.delete()
            return JsonResponse({'message': 'Dům byl odstraněn'}, status=200)
        except House.DoesNotExist:
            return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "PATCH":
        try:
            house_id = request.GET.get('id')
            if not house_id:
                return JsonResponse({'error': 'Chybí ID domu'}, status=400)
                
            house = House.objects.get(id=house_id)
            data = json.loads(request.body)
            
            if 'name' in data:
                house.name = data['name']
            if 'solar_power' in data:
                house.solar_power = data['solar_power']
            if 'battery_capacity' in data:
                house.battery_capacity = data['battery_capacity']
            
            house.save()
            
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity
            })
            
        except House.DoesNotExist:
            return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)