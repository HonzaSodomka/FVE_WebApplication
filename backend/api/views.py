"""
API endpointy pro FVE aplikaci pro optimalizaci nabíjení baterie.
"""

from django.http import JsonResponse
from .models import ChargingData, ConsumptionData, PriceData, SolarData, House, Appliance, ChargingSchedule
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
import json


logger = logging.getLogger('api')


def get_prices(request):
    """Vrací hodinová cenová data elektřiny pro zadaný den."""
    date_str = request.GET.get('date')
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        prices = PriceData.objects.filter(date=date)
        
        if not prices.exists():
            logger.warning(f"No price data found for date {date}")
            return JsonResponse(
               {'error': 'No data available for this date'}, 
               status=404
            )
       
        data = [{
            'hour': price.hour,
            'price_czk': price.price_czk,
            'level': price.level,
            'level_num': price.level_num
        } for price in prices]
       
        return JsonResponse({'prices': data})
       
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return JsonResponse(
            {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
            status=400
        )
    except Exception as e:
        logger.error(f"Unexpected error when getting prices: {str(e)}")
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )
    

def get_solar_prediction(request):
    """Vrací predikci solární výroby pro zadaný den a výkon."""
    date_str = request.GET.get('date')
    power = float(request.GET.get('power', 10))
   
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        solar_data = SolarData.objects.filter(
            timestamp__date=date
        ).order_by('timestamp')
        
        if not solar_data.exists():
            logger.warning(f"No solar data found for date {date}")
            return JsonResponse(
                {'error': 'No data available for this date'}, 
                status=404
            )
        
        power_ratio = power / 20
        data = [{
            'timestamp': solar.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'watts': solar.watts * power_ratio,
            'watt_hours_period': solar.watt_hours_period * power_ratio,
            'watt_hours_cumulative': solar.watt_hours_cumulative * power_ratio,
            'hour': solar.timestamp.hour
        } for solar in solar_data]
        
        daily_total = (solar_data.last().watt_hours_cumulative * power_ratio) if solar_data.exists() else 0
        
        response = {
            'predictions': data,
            'daily_total': daily_total
        }
        
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
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE", "PATCH"])
def houses(request):
    """Endpoint pro správu domů."""
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
                current_battery_level=data.get('current_battery_level', 0),
                min_battery_level=data.get('min_battery_level', 10),
                charging_efficiency=data.get('charging_efficiency', 90),
                discharging_efficiency=data.get('discharging_efficiency', 90),
                risk_level=data.get('risk_level', 'MEDIUM'),
                solar_variation=data.get('solar_variation', 1)
            )
            
            logger.info(f"Created house with ID {house.id}")
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
            logger.error(f"Missing field: {str(e)}")
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
            logger.info(f"Deleted house with ID {house_id}")
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
            logger.info(f"Updated house {house_id}")
            
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
            return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating house: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        

@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE", "PATCH"])
def house_appliances(request, house_id):
    """Endpoint pro správu spotřebičů v domě."""
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
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
                'next_start_time',
                'priority_level', 'interruptible', 'inactive_windows'
            ))
            return JsonResponse({'appliances': appliances})
        except Exception as e:
            logger.error(f"Error fetching appliances: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
        
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            
            appliance_data = {
                'house': house,
                'name': data['name'],
                'power_consumption': data['power_consumption'],
                'appliance_type': data['appliance_type'],
                'priority_level': data.get('priority_level', 1),
                'interruptible': data.get('interruptible', True),
            }

            if data['appliance_type'] == 'CYCLIC':
                if 'standby_power' not in data:
                    return JsonResponse({'error': 'Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu'}, status=400)
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data['standby_power'],
                    run_duration_min=data['run_duration_min'],
                    run_duration_max=data['run_duration_max'],
                    pause_duration_min=data['pause_duration_min'],
                    pause_duration_max=data['pause_duration_max'],
                    inactive_windows=data.get('inactive_windows', [])
                )
            elif data['appliance_type'] == 'SCHEDULED':
                # Zajistíme, že všechna časová okna mají is_active
                weekday_hours = data.get('weekday_hours', None)
                weekend_hours = data.get('weekend_hours', None)
                
                if weekday_hours:
                    for window in weekday_hours:
                        if 'is_active' not in window:
                            window['is_active'] = True
                
                if weekend_hours:
                    for window in weekend_hours:
                        if 'is_active' not in window:
                            window['is_active'] = True
                            
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data.get('standby_power', 0),
                    usage_duration_min=data['usage_duration_min'],
                    usage_duration_max=data['usage_duration_max'],
                    weekday_hours=weekday_hours,
                    weekend_hours=weekend_hours,
                    inactive_windows=data.get('inactive_windows', [])
                )
            elif data['appliance_type'] == 'ON_DEMAND':
                # Zajistíme, že všechna časová okna mají is_active
                weekday_hours = data.get('weekday_hours', None)
                weekend_hours = data.get('weekend_hours', None)
                
                if weekday_hours:
                    for window in weekday_hours:
                        if 'is_active' not in window:
                            window['is_active'] = True
                
                if weekend_hours:
                    for window in weekend_hours:
                        if 'is_active' not in window:
                            window['is_active'] = True
                            
                appliance = Appliance.objects.create(
                    **appliance_data,
                    standby_power=data.get('standby_power', 0),
                    usage_duration_min=data['usage_duration_min'],
                    usage_duration_max=data['usage_duration_max'],
                    weekday_hours=weekday_hours,
                    weekend_hours=weekend_hours,
                    remaining_minutes_list=[],
                    planned_starts=[],
                    inactive_windows=data.get('inactive_windows', [])
                )
            elif data['appliance_type'] == 'CONSTANT':
                appliance = Appliance.objects.create(
                    **appliance_data,
                    inactive_windows=data.get('inactive_windows', [])
                )
            else:
                logger.error(f"Unknown appliance type: {data['appliance_type']}")
                return JsonResponse({'error': 'Neznámý typ spotřebiče'}, status=400)
            
            logger.info(f"Created appliance {appliance.id} for house {house_id}")
            
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
                'next_start_time': appliance.next_start_time,
                'priority_level': appliance.priority_level,
                'interruptible': appliance.interruptible,
                'inactive_windows': appliance.inactive_windows
            })
            
        except KeyError as e:
            logger.error(f"Missing field: {str(e)}")
            return JsonResponse({'error': f'Chybějící pole: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Error creating appliance: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "DELETE":
        try:
            appliance_id = request.GET.get('id')
            if not appliance_id:
                return JsonResponse({'error': 'Chybí ID spotřebiče'}, status=400)
                
            appliance = Appliance.objects.get(id=appliance_id, house=house)
            appliance.delete()
            logger.info(f"Deleted appliance {appliance_id}")
            return JsonResponse({'message': 'Spotřebič byl odstraněn'}, status=200)
            
        except Appliance.DoesNotExist:
            return JsonResponse({'error': 'Spotřebič nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting appliance: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)
            
    elif request.method == "PATCH":
        try:
            appliance_id = request.GET.get('id')
            if not appliance_id:
                return JsonResponse({'error': 'Chybí ID spotřebiče'}, status=400)
                
            appliance = Appliance.objects.get(id=appliance_id, house=house)
            data = json.loads(request.body)
            
            # Aktualizace základních polí
            if 'name' in data:
                appliance.name = data['name']
            if 'power_consumption' in data:
                appliance.power_consumption = data['power_consumption']
            if 'appliance_type' in data:
                appliance.appliance_type = data['appliance_type']
                
            # Aktualizace polí pro optimalizaci
            if 'priority_level' in data:
                appliance.priority_level = data['priority_level']
            if 'interruptible' in data:
                appliance.interruptible = data['interruptible']
            if 'inactive_windows' in data:
                appliance.inactive_windows = data['inactive_windows']

            # Typ-specifické aktualizace
            if appliance.appliance_type == 'CYCLIC':
                if 'standby_power' in data:
                    appliance.standby_power = data['standby_power']
                elif not appliance.standby_power:
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
                elif appliance.standby_power is None:
                    appliance.standby_power = 0
                    
                if 'usage_duration_min' in data:
                    appliance.usage_duration_min = data['usage_duration_min']
                if 'usage_duration_max' in data:
                    appliance.usage_duration_max = data['usage_duration_max']
                    
                # Zajistíme, že všechna časová okna mají is_active
                if 'weekday_hours' in data:
                    weekday_hours = data['weekday_hours']
                    if weekday_hours:
                        for i, window in enumerate(weekday_hours):
                            if 'is_active' not in window:
                                weekday_hours[i]['is_active'] = True
                    appliance.weekday_hours = weekday_hours
                    
                if 'weekend_hours' in data:
                    weekend_hours = data['weekend_hours']
                    if weekend_hours:
                        for i, window in enumerate(weekend_hours):
                            if 'is_active' not in window:
                                weekend_hours[i]['is_active'] = True
                    appliance.weekend_hours = weekend_hours
            
            elif appliance.appliance_type == 'CONSTANT':
                appliance.standby_power = None
            
            appliance.save()
            logger.info(f"Updated appliance {appliance_id}")
            
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
                'next_start_time': appliance.next_start_time,
                'priority_level': appliance.priority_level,
                'interruptible': appliance.interruptible,
                'inactive_windows': appliance.inactive_windows
            })
            
        except Appliance.DoesNotExist:
            return JsonResponse({'error': 'Spotřebič nenalezen'}, status=404)
        except Exception as e:
            logger.error(f"Error updating appliance: {str(e)}")
            return JsonResponse({'error': 'Interní chyba serveru'}, status=500)


@require_http_methods(["GET"])
def consumption_data(request, house_id):
    """Endpoint pro získání hodinových dat o spotřebě."""
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return JsonResponse({'error': 'Chybí parametr date'}, status=400)
            
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        consumption = ConsumptionData.objects.filter(
            house=house,
            date=date
        ).order_by('time')
        
        hourly_consumption = {}
        daily_total = 0
        
        for record in consumption:
            hour = int(record.time.split(':')[0])
            
            if hour not in hourly_consumption:
                hourly_consumption[hour] = 0
            
            minute_consumption = sum(
                item['consumption_w'] 
                for item in record.appliance_consumption
            )
            
            hourly_consumption[hour] += minute_consumption
        
        data = []
        for hour, consumption_wh in sorted(hourly_consumption.items()):
            hourly_wh = round(consumption_wh, 2)
            data.append({
                'hour': hour,
                'consumption_wh': hourly_wh
            })
            daily_total += hourly_wh
        
        current_time = datetime.now()
        
        return JsonResponse({
            'consumption': data,
            'daily_total': round(daily_total, 2),
            'current_time': current_time.isoformat()
        })
        
    except ValueError:
        logger.error(f"Invalid date format")
        return JsonResponse({'error': 'Neplatný formát data'}, status=400)
    except Exception as e:
        logger.error(f"Error fetching consumption: {str(e)}")
        return JsonResponse({'error': 'Interní chyba serveru'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_simulation(request, house_id):
    """Zapíná nebo vypíná simulaci pro daný dům."""
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


@require_http_methods(["GET"])
def charging_data(request, house_id):
    """Endpoint pro získání dat o nabíjení."""
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return JsonResponse({'error': 'Chybí parametr date'}, status=400)
            
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        charging = ChargingData.objects.filter(
            house=house,
            date=date
        ).first()
        
        if not charging:
            return JsonResponse({
                'solar_charged_kwh': 0,
                'grid_charged_kwh': 0,
                'grid_charged_cost': 0
            })
        
        return JsonResponse({
            'solar_charged_kwh': charging.solar_charged_kwh,
            'grid_charged_kwh': charging.grid_charged_kwh,
            'grid_charged_cost': charging.grid_charged_cost
        })
        
    except ValueError:
        logger.error(f"Invalid date format")
        return JsonResponse({'error': 'Neplatný formát data'}, status=400)
    except Exception as e:
        logger.error(f"Error fetching charging data: {str(e)}")
        return JsonResponse({'error': 'Interní chyba serveru'}, status=500)


@require_http_methods(["GET"])
def charging_schedule(request, house_id):
    """Vrací plánované nabíjení ze sítě pro daný dům a datum."""
    try:
        house = House.objects.get(id=house_id)
    except House.DoesNotExist:
        return JsonResponse({'error': 'Dům nenalezen'}, status=404)
        
    try:
        date_str = request.GET.get('date')
        if not date_str:
            return JsonResponse({'error': 'Chybí parametr date'}, status=400)
            
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Omezení pouze na aktuální a následující den
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        if date < today:
            return JsonResponse({
                'schedule': [],
                'message': 'Plán nabíjení je dostupný pouze pro aktuální a následující den'
            })
            
        if date > tomorrow:
            return JsonResponse({
                'schedule': [],
                'message': 'Plán nabíjení je dostupný pouze pro aktuální a následující den'
            })
        
        schedule = ChargingSchedule.objects.filter(
            house=house,
            date=date
        ).order_by('hour')
        
        schedule_data = []
        for item in schedule:
            schedule_data.append({
                'hour': item.hour,
                'planned_charging_kwh': item.planned_charging_kwh
            })
        
        # Přidáváme informativní zprávu, pokud není naplánováno žádné nabíjení
        message = None
        if not schedule_data:
            if date == today:
                message = "Pro dnešní den není naplánováno žádné nabíjení ze sítě"
            else:
                message = "Pro zítřejší den není naplánováno žádné nabíjení ze sítě"
        
        return JsonResponse({
            'schedule': schedule_data,
            'message': message
        })
        
    except ValueError:
        logger.error(f"Invalid date format")
        return JsonResponse({'error': 'Neplatný formát data'}, status=400)
    except Exception as e:
        logger.error(f"Error fetching charging schedule: {str(e)}")
        return JsonResponse({'error': 'Interní chyba serveru'}, status=500)