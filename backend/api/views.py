from django.http import JsonResponse
from .models import PriceData, SolarData, House, Appliance, DashboardPassword
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import check_password
import logging
import json


logger = logging.getLogger('api')

@csrf_exempt
@require_http_methods(["POST"])
def verify_password(request):
    try:
        data = json.loads(request.body)
        password = data.get('password')
        
        dashboard_password = DashboardPassword.objects.first()
        if not dashboard_password:
            return JsonResponse({
                'error': 'Systémová chyba - heslo není nastaveno'
            }, status=500)
        
        # Porovnání zahashovaného hesla
        if check_password(password, dashboard_password.password_hash):
            # Nastavení session
            request.session['authenticated'] = True
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Nesprávné heslo'}, status=401)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    # Vrací list domů z db
    if request.method == "GET":
        try:
            houses_list = list(House.objects.values())
            logger.info(f"Successfully returned {len(houses_list)} houses")
            return JsonResponse({'houses': houses_list})
        except Exception as e:
            logger.error(f"Error fetching houses: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)

    # Vytváří dům v db   
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.info(f"Received request to create house: {data}")
            house = House.objects.create(
                name=data['name'],
                solar_power=data['solar_power'],
                battery_capacity=data['battery_capacity']
            )
            logger.info(f"Successfully created house with ID {house.id}")
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity
            }, status=201)
        except KeyError as e:
            logger.error(f"Missing field in house creation request: {str(e)}")
            return JsonResponse({'error': f'Chybějící pole: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error creating house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)

    # Maže dům z db        
    elif request.method == "DELETE":
        try:
            house_id = request.GET.get('id')
            if not house_id:
                logger.warning("Delete request missing house ID")
                return JsonResponse({'error': 'Chybí ID domu'}, status=400)
                
            house = House.objects.get(id=house_id)
            house.delete()
            logger.info(f"Successfully deleted house with ID {house_id}")
            return JsonResponse({'message': 'Dům byl odstraněn'}, status=200)
        except House.DoesNotExist:
            logger.warning(f"Attempted to delete non-existent house with ID {house_id}")
            return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)

    # Aktualizuje dům již existující v db        
    elif request.method == "PATCH":
        try:
            house_id = request.GET.get('id')
            if not house_id:
                logger.warning("Update request missing house ID")
                return JsonResponse({'error': 'Chybí ID domu'}, status=400)
                
            house = House.objects.get(id=house_id)
            data = json.loads(request.body)
            logger.info(f"Received request to update house {house_id}: {data}")
            
            if 'name' in data:
                house.name = data['name']
            if 'solar_power' in data:
                house.solar_power = data['solar_power']
            if 'battery_capacity' in data:
                house.battery_capacity = data['battery_capacity']
            
            house.save()
            logger.info(f"Successfully updated house {house_id}")
            
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity
            })
            
        except House.DoesNotExist:
            logger.warning(f"Attempted to update non-existent house with ID {house_id}")
            return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        
@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE", "PATCH"])
def house_appliances(request, house_id):
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
        logger.warning(f"Attempted to access appliances for non-existent house with ID {house_id}")
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        
    if request.method == "GET":
        try:
            appliances = list(house.appliances.values())
            logger.info(f"Successfully returned {len(appliances)} appliances for house {house_id}")
            return JsonResponse({'appliances': appliances})
        except Exception as e:
            logger.error(f"Error fetching appliances for house {house_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.info(f"Received request to create appliance for house {house_id}: {data}")
            
            # Příprava společných dat pro spotřebič
            appliance_data = {
                'house': house,
                'name': data['name'],
                'power_consumption': data['power_consumption'],
                'appliance_type': data['appliance_type']
            }
            # Vytvoření spotřebiče s ohledem na jeho typ
            if data['appliance_type'] == 'CYCLIC':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    run_duration_min=data['run_duration_min'],
                    run_duration_max=data['run_duration_max'],
                    pause_duration_min=data['pause_duration_min'],
                    pause_duration_max=data['pause_duration_max']
                )
            elif data['appliance_type'] == 'SCHEDULED':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    usage_duration=data['usage_duration'],
                    weekday_probability=data.get('weekday_probability', 1.0),
                    weekend_probability=data.get('weekend_probability', 1.0),
                    weekday_hours=data.get('weekday_hours', [[0, 24]]),
                    weekend_hours=data.get('weekend_hours', [[0, 24]])
                )
            elif data['appliance_type'] == 'ON_DEMAND':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    usage_duration=data['usage_duration'],
                    weekday_probability=data.get('weekday_probability', 1.0),
                    weekend_probability=data.get('weekend_probability', 1.0),
                    weekday_hours=data.get('weekday_hours', [[0, 24]]),
                    weekend_hours=data.get('weekend_hours', [[0, 24]]),
                    uses_per_window=data['uses_per_window']
                )
            elif data['appliance_type'] == 'CONSTANT':
                appliance = Appliance.objects.create(**appliance_data)
            else:
                # Neznámý typ spotřebiče
                logger.error(f"Unknown appliance type: {data['appliance_type']}")
                return JsonResponse({'error': 'Neznámý typ spotřebiče'}, status=400)
            
            logger.info(f"Successfully created appliance {appliance.id} for house {house_id}")
            
            # Vrácení všech polí objektu
            return JsonResponse({
                'id': appliance.id,
                'name': appliance.name,
                'power_consumption': appliance.power_consumption,
                'appliance_type': appliance.appliance_type,
                'run_duration_min': appliance.run_duration_min,
                'run_duration_max': appliance.run_duration_max,
                'pause_duration_min': appliance.pause_duration_min,
                'pause_duration_max': appliance.pause_duration_max,
                'usage_duration': appliance.usage_duration,
                'uses_per_window': appliance.uses_per_window,
                'weekday_probability': appliance.weekday_probability,
                'weekend_probability': appliance.weekend_probability,
                'weekday_hours': appliance.weekday_hours,
                'weekend_hours': appliance.weekend_hours
            }, status=201)
            
        except KeyError as e:
            logger.error(f"Missing field in appliance creation request: {str(e)}")
            return JsonResponse({'error': f'Chybějící pole: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error creating appliance for house {house_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "DELETE":
        try:
            appliance_id = request.GET.get('id')
            if not appliance_id:
                logger.warning("Delete request missing appliance ID")
                return JsonResponse({'error': 'Chybí ID spotřebiče'}, status=400)
                
            appliance = Appliance.objects.get(id=appliance_id, house=house)
            appliance.delete()
            logger.info(f"Successfully deleted appliance {appliance_id} from house {house_id}")
            return JsonResponse({'message': 'Spotřebič byl odstraněn'}, status=200)
            
        except Appliance.DoesNotExist:
            logger.warning(f"Attempted to delete non-existent appliance {appliance_id} from house {house_id}")
            return JsonResponse({'error': 'Spotřebič nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting appliance {appliance_id} from house {house_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "PATCH":
        try:
            appliance_id = request.GET.get('id')
            if not appliance_id:
                logger.warning("Update request missing appliance ID")
                return JsonResponse({'error': 'Chybí ID spotřebiče'}, status=400)
                
            appliance = Appliance.objects.get(id=appliance_id, house=house)
            data = json.loads(request.body)
            logger.info(f"Received request to update appliance {appliance_id}: {data}")
            
            # Základní pole
            if 'name' in data:
                appliance.name = data['name']
            if 'power_consumption' in data:
                appliance.power_consumption = data['power_consumption']
            if 'appliance_type' in data:
                appliance.appliance_type = data['appliance_type']

            # Pole podle typu spotřebiče
            if appliance.appliance_type == 'CYCLIC':
                if 'run_duration_min' in data:
                    appliance.run_duration_min = data['run_duration_min']
                if 'run_duration_max' in data:
                    appliance.run_duration_max = data['run_duration_max']
                if 'pause_duration_min' in data:
                    appliance.pause_duration_min = data['pause_duration_min']
                if 'pause_duration_max' in data:
                    appliance.pause_duration_max = data['pause_duration_max']
                    
            elif appliance.appliance_type in ['SCHEDULED', 'ON_DEMAND']:
                if 'usage_duration' in data:
                    appliance.usage_duration = data['usage_duration']
                if 'weekday_probability' in data:
                    appliance.weekday_probability = data['weekday_probability']
                if 'weekend_probability' in data:
                    appliance.weekend_probability = data['weekend_probability']
                if 'weekday_hours' in data:
                    appliance.weekday_hours = data['weekday_hours']
                if 'weekend_hours' in data:
                    appliance.weekend_hours = data['weekend_hours']
                    
                if appliance.appliance_type == 'ON_DEMAND':
                    if 'uses_per_window' in data:
                        appliance.uses_per_window = data['uses_per_window']
            
            appliance.save()
            logger.info(f"Successfully updated appliance {appliance_id}")
            
            return JsonResponse({
                'id': appliance.id,
                'name': appliance.name,
                'power_consumption': appliance.power_consumption,
                'appliance_type': appliance.appliance_type,
                'run_duration_min': appliance.run_duration_min,
                'run_duration_max': appliance.run_duration_max,
                'pause_duration_min': appliance.pause_duration_min,
                'pause_duration_max': appliance.pause_duration_max,
                'usage_duration': appliance.usage_duration,
                'uses_per_window': appliance.uses_per_window,
                'weekday_probability': appliance.weekday_probability,
                'weekend_probability': appliance.weekend_probability,
                'weekday_hours': appliance.weekday_hours,
                'weekend_hours': appliance.weekend_hours
            })
            
        except Appliance.DoesNotExist:
            logger.warning(f"Attempted to update non-existent appliance {appliance_id}")
            return JsonResponse({'error': 'Spotřebič nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating appliance {appliance_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)