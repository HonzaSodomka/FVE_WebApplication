from django.http import JsonResponse
from .models import ConsumptionData, PriceData, SolarData, House, Appliance
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
    # Získáme power parametr s výchozí hodnotou 10
    power = float(request.GET.get('power', 10))
    logger.info(f"Received get_solar_prediction request for {date_str} with power {power}kWp")
   
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        logger.debug(f"Successfully parsed date {date}")
        
        solar_data = SolarData.objects.filter(
            timestamp__date=date
        ).order_by('timestamp')
        
        if not solar_data.exists():
            logger.warning(f"No solar data found for date {date}")
            return JsonResponse(
                {'error': 'No data available for this date'}, 
                status=404
            )
        
        # Přepočítáme hodnoty - nejdřív vydělíme 20 (původní výkon) a pak vynásobíme požadovaným výkonem
        power_ratio = power / 20
        data = [{
            'timestamp': solar.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'watts': solar.watts * power_ratio,
            'watt_hours_period': solar.watt_hours_period * power_ratio,
            'watt_hours_cumulative': solar.watt_hours_cumulative * power_ratio,
            'hour': solar.timestamp.hour
        } for solar in solar_data]
        
        # Přepočítáme i denní součet
        daily_total = (solar_data.last().watt_hours_cumulative * power_ratio) if solar_data.exists() else 0
        
        response = {
            'predictions': data,
            'daily_total': daily_total
        }
        
        logger.info(f"Successfully returned {len(data)} solar predictions for {date} with power {power}kWp (daily total: {daily_total}Wh)")
        return JsonResponse(response)
        
    except ValueError as e:
        if 'power' in str(e):
            logger.error(f"Invalid power value: {request.GET.get('power')}")
            return JsonResponse({
                'error': 'Invalid power value. Must be a number.',
                'detail': str(e)
            }, status=400)
        
        logger.error(f"Invalid date format: {date_str}")
        return JsonResponse({
            'error': 'Invalid date format. Use YYYY-MM-DD',
            'detail': str(e)
        }, status=400)
    except Exception as e:
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
            
            required_fields = ['name', 'solar_power', 'battery_capacity', 'max_charging_power', 'max_discharging_power']
            for field in required_fields:
                if field not in data:
                    raise KeyError(field)
            
            house = House.objects.create(
                name=data['name'],
                solar_power=data['solar_power'],
                battery_capacity=data['battery_capacity'],
                max_charging_power=data['max_charging_power'],
                max_discharging_power=data['max_discharging_power'],
                # Volitelná pole s výchozími hodnotami
                current_battery_level=data.get('current_battery_level', 0),
                min_battery_level=data.get('min_battery_level', 10),
                charging_efficiency=data.get('charging_efficiency', 90),
                discharging_efficiency=data.get('discharging_efficiency', 90),
                risk_level=data.get('risk_level', 'MEDIUM'),
                solar_variation=data.get('solar_variation', 1)
            )
            
            logger.info(f"Successfully created house with ID {house.id}")
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity,
                'current_battery_level': house.current_battery_level,
                'min_battery_level': house.min_battery_level,
                'max_charging_power': house.max_charging_power,
                'max_discharging_power': house.max_discharging_power,
                'charging_efficiency': house.charging_efficiency,
                'discharging_efficiency': house.discharging_efficiency,
                'risk_level': house.risk_level,
                'is_active': house.is_active,
                'solar_variation': house.solar_variation
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
            
            updatable_fields = [
                'name', 'solar_power', 'battery_capacity', 'current_battery_level',
                'min_battery_level', 'max_charging_power', 'max_discharging_power',
                'charging_efficiency', 'discharging_efficiency', 'risk_level',
                'solar_variation'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(house, field, data[field])
            
            house.save()
            logger.info(f"Successfully updated house {house_id}")
            
            return JsonResponse({
                'id': house.id,
                'name': house.name,
                'solar_power': house.solar_power,
                'battery_capacity': house.battery_capacity,
                'current_battery_level': house.current_battery_level,
                'min_battery_level': house.min_battery_level,
                'max_charging_power': house.max_charging_power,
                'max_discharging_power': house.max_discharging_power,
                'charging_efficiency': house.charging_efficiency,
                'discharging_efficiency': house.discharging_efficiency,
                'risk_level': house.risk_level,
                'is_active': house.is_active,
                'solar_variation': house.solar_variation
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
            appliances = list(house.appliances.values(
                'id', 'name', 'power_consumption', 'standby_power', 'appliance_type',
                'run_duration_min', 'run_duration_max',
                'pause_duration_min', 'pause_duration_max',
                'usage_duration_min', 'usage_duration_max',
                'weekday_hours', 'weekend_hours',
                'remaining_minutes_list', 'planned_starts',
                'is_active', 'in_standby', 'remaining_minutes',
                'next_start_time'
            ))
            logger.info(f"Successfully returned {len(appliances)} appliances for house {house_id}")
            return JsonResponse({'appliances': appliances})
        except Exception as e:
            logger.error(f"Error fetching appliances for house {house_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.info(f"Received request to create appliance for house {house_id}: {data}")
            
            appliance_data = {
                'house': house,
                'name': data['name'],
                'power_consumption': data['power_consumption'],
                'appliance_type': data['appliance_type']
            }

            # Zpracování standby_power podle typu spotřebiče
            if data['appliance_type'] == 'CYCLIC':
                if 'standby_power' not in data:
                    return JsonResponse({'error': 'Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu'}, status=400)
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data['standby_power'],
                    run_duration_min=data['run_duration_min'],
                    run_duration_max=data['run_duration_max'],
                    pause_duration_min=data['pause_duration_min'],
                    pause_duration_max=data['pause_duration_max']
                )
            elif data['appliance_type'] == 'SCHEDULED':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data.get('standby_power', 0),
                    usage_duration_min=data['usage_duration_min'],
                    usage_duration_max=data['usage_duration_max'],
                    weekday_hours=data.get('weekday_hours', None),
                    weekend_hours=data.get('weekend_hours', None),
                )
            elif data['appliance_type'] == 'ON_DEMAND':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data.get('standby_power', 0),
                    usage_duration_min=data['usage_duration_min'],
                    usage_duration_max=data['usage_duration_max'],
                    weekday_hours=data.get('weekday_hours', None),
                    weekend_hours=data.get('weekend_hours', None),
                    remaining_minutes_list=[],
                    planned_starts=[]
                )
            elif data['appliance_type'] == 'CONSTANT':
                appliance = Appliance.objects.create(**appliance_data)
            else:
                logger.error(f"Unknown appliance type: {data['appliance_type']}")
                return JsonResponse({'error': 'Neznámý typ spotřebiče'}, status=400)
            
            logger.info(f"Successfully created appliance {appliance.id} for house {house_id}")
            
            return JsonResponse({
                'id': appliance.id,
                'name': appliance.name,
                'power_consumption': appliance.power_consumption,
                'standby_power': appliance.standby_power,
                'appliance_type': appliance.appliance_type,
                'run_duration_min': appliance.run_duration_min,
                'run_duration_max': appliance.run_duration_max,
                'pause_duration_min': appliance.pause_duration_min,
                'pause_duration_max': appliance.pause_duration_max,
                'usage_duration_min': appliance.usage_duration_min,
                'usage_duration_max': appliance.usage_duration_max,
                'weekday_hours': appliance.weekday_hours,
                'weekend_hours': appliance.weekend_hours,
                'remaining_minutes_list': appliance.remaining_minutes_list,
                'planned_starts': appliance.planned_starts,
                'is_active': appliance.is_active,
                'in_standby': appliance.in_standby,
                'remaining_minutes': appliance.remaining_minutes,
                'next_start_time': appliance.next_start_time
            })
            
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
            
            if 'name' in data:
                appliance.name = data['name']
            if 'power_consumption' in data:
                appliance.power_consumption = data['power_consumption']
            if 'appliance_type' in data:
                appliance.appliance_type = data['appliance_type']

            # Nastavení standby_power podle typu spotřebiče
            if appliance.appliance_type == 'CYCLIC':
                if 'standby_power' in data:
                    appliance.standby_power = data['standby_power']
                elif not appliance.standby_power:  # Pokud se mění typ na CYCLIC a není nastaven standby_power
                    return JsonResponse({'error': 'Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu'}, status=400)
                
                if 'run_duration_min' in data:
                    appliance.run_duration_min = data['run_duration_min']
                if 'run_duration_max' in data:
                    appliance.run_duration_max = data['run_duration_max']
                if 'pause_duration_min' in data:
                    appliance.pause_duration_min = data['pause_duration_min']
                if 'pause_duration_max' in data:
                    appliance.pause_duration_max = data['pause_duration_max']
                    
            elif appliance.appliance_type in ['SCHEDULED', 'ON_DEMAND']:
                if 'standby_power' in data:
                    appliance.standby_power = data['standby_power']
                elif appliance.standby_power is None:  # Při změně typu nastavíme default 0
                    appliance.standby_power = 0
                    
                if 'usage_duration_min' in data:
                    appliance.usage_duration_min = data['usage_duration_min']
                if 'usage_duration_max' in data:
                    appliance.usage_duration_max = data['usage_duration_max']
                if 'weekday_hours' in data:
                    appliance.weekday_hours = data['weekday_hours']
                if 'weekend_hours' in data:
                    appliance.weekend_hours = data['weekend_hours']
            
            elif appliance.appliance_type == 'CONSTANT':
                appliance.standby_power = None
            
            appliance.save()
            logger.info(f"Successfully updated appliance {appliance_id}")
            
            return JsonResponse({
                'id': appliance.id,
                'name': appliance.name,
                'power_consumption': appliance.power_consumption,
                'standby_power': appliance.standby_power,
                'appliance_type': appliance.appliance_type,
                'run_duration_min': appliance.run_duration_min,
                'run_duration_max': appliance.run_duration_max,
                'pause_duration_min': appliance.pause_duration_min,
                'pause_duration_max': appliance.pause_duration_max,
                'usage_duration_min': appliance.usage_duration_min,
                'usage_duration_max': appliance.usage_duration_max,
                'weekday_hours': appliance.weekday_hours,
                'weekend_hours': appliance.weekend_hours,
                'remaining_minutes_list': appliance.remaining_minutes_list,
                'planned_starts': appliance.planned_starts,
                'is_active': appliance.is_active,
                'in_standby': appliance.in_standby,
                'remaining_minutes': appliance.remaining_minutes,
                'next_start_time': appliance.next_start_time
            })
            
        except Appliance.DoesNotExist:
            logger.warning(f"Attempted to update non-existent appliance {appliance_id}")
            return JsonResponse({'error': 'Spotřebič nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating appliance {appliance_id}: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def consumption_data(request, house_id):
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
        logger.warning(f"Attempted to access consumption for non-existent house with ID {house_id}")
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        
    if request.method == "GET":
        try:
            date_str = request.GET.get('date')
            if not date_str:
                return JsonResponse({'error': 'Chybí parametr date'}, status=400)
                
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Získá všechny záznamy pro daný den
            consumption = ConsumptionData.objects.filter(
                house=house,
                date=date
            ).order_by('time')
            
            # Slovník pro ukládání hodinové spotřeby
            hourly_consumption = {}
            daily_total = 0  # Celková denní spotřeba
            
            # Zpracování dat po minutách do hodinových součtů
            for record in consumption:
                hour = int(record.time.split(':')[0])  # Používáme přímo hodinu bez posunutí
                
                if hour not in hourly_consumption:
                    hourly_consumption[hour] = 0
                
                minute_consumption = sum(
                    item['consumption_w'] 
                    for item in record.appliance_consumption
                )
                
                hourly_consumption[hour] += minute_consumption
            
            # Formátování výstupu a výpočet denního součtu
            data = []
            for hour, consumption_wh in sorted(hourly_consumption.items()):
                hourly_wh = round(consumption_wh, 2)
                data.append({
                    'hour': hour,
                    'consumption_wh': hourly_wh
                })
                daily_total += hourly_wh
            
            # Přidání aktuálního času serveru
            current_time = datetime.now()
            
            logger.info(f"Successfully returned hourly consumption for house {house_id} on {date} (total: {daily_total:.2f} Wh)")
            return JsonResponse({
                'consumption': data,
                'daily_total': round(daily_total, 2),
                'current_time': current_time.isoformat()
            })
            
        except ValueError:
            logger.error(f"Invalid date format received: {date_str}")
            return JsonResponse({'error': 'Neplatný formát data'}, status=400)
        except Exception as e:
            logger.error(f"Error fetching consumption: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    # POST - zůstává beze změny pro ukládání minutových dat
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            timestamp = datetime.strptime(data['timestamp'], '%Y-%m-%d %H:%M:%S')
            date = timestamp.date()
            time = timestamp.strftime('%H:%M')
            appliance_consumption = data['appliances']
            
            consumption, created = ConsumptionData.objects.update_or_create(
                house=house,
                date=date,
                time=time,
                defaults={'appliance_consumption': appliance_consumption}
            )
            
            action = "vytvořena" if created else "aktualizována"
            logger.info(f"Spotřeba pro dům {house.id} byla {action} (datum: {date}, čas: {time})")
            
            return JsonResponse({'message': 'Data uložena'})
            
        except KeyError as e:
            logger.error(f"Chybějící pole v požadavku: {str(e)}")
            return JsonResponse({'error': f'Chybějící pole: {str(e)}'}, status=400)
        except ValueError as e:
            logger.error(f"Neplatný formát dat: {str(e)}")
            return JsonResponse({'error': f'Neplatná data: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error saving consumption: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def toggle_simulation(request, house_id):
    try:
        house = House.objects.get(id=house_id)
        
        data = json.loads(request.body)
        is_active = data.get('is_active')
        
        if is_active is None:
            return JsonResponse({'error': 'Chybí parametr is_active'}, status=400)
            
        house.is_active = is_active
        house.save()
        
        logger.info(f"Simulace pro dům {house.id} byla {'spuštěna' if is_active else 'zastavena'}")
        
        return JsonResponse({
            'id': house.id,
            'name': house.name,
            'is_active': house.is_active
        })
        
    except House.DoesNotExist:
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
    except Exception as e:
        logger.error(f"Error toggling simulation: {str(e)}")
        return JsonResponse({'error': 'Interní chyba serveru'}, status=500)