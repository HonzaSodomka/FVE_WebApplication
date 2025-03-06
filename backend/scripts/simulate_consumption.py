import psycopg2
from datetime import datetime
import logging
import json
import random

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def is_peak_time(current_time, is_weekend):
    """
    Určí, zda je aktuální čas ve špičce podle dne v týdnu
    """
    hour = current_time.hour
    
    if is_weekend:
        # Víkendové špičky: 8-10, 11-13, 17-20
        return (8 <= hour < 10) or (11 <= hour < 13) or (17 <= hour < 20)
    else:
        # Špičky ve všední dny: 6-8, 17-20
        return (6 <= hour < 8) or (17 <= hour < 20)

def get_adjusted_duration(min_duration, max_duration, is_peak_time, for_active_state):
    """
    Upraví délku běhu/standby podle toho, zda je špička a podle typu stavu
    """
    if is_peak_time:
        if for_active_state:
            # Ve špičce prodloužíme aktivní běh - použijeme horní polovinu rozsahu
            range_size = max_duration - min_duration
            half_range = range_size // 2
            adjusted_min = min_duration + half_range
            adjusted_max = max_duration
        else:
            # Ve špičce zkrátíme standby NA POLOVINU
            adjusted_min = min_duration // 2
            adjusted_max = max_duration // 2
    else:
        # Mimo špičku použijeme celý rozsah
        adjusted_min = min_duration
        adjusted_max = max_duration
        
    return random.randint(adjusted_min, adjusted_max)

def simulate_minute_consumption():
    try:
        logger.info("ZAHAJUJI SIMULACI SPOTŘEBY")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        current_time = datetime.now().replace(second=0, microsecond=0)
        current_date = current_time.date()
        current_time_str = current_time.strftime('%H:%M')
        is_weekend = current_time.weekday() >= 5
        logger.info(f"Simuluji pro čas: {current_date} {current_time_str} ({'víkend' if is_weekend else 'pracovní den'})")
        
        # Načteme spotřebiče aktivních domů
        cur.execute("""
            SELECT 
                h.id as house_id,
                a.id as appliance_id,
                a.power_consumption,
                a.standby_power,
                a.appliance_type,
                a.is_active,
                a.in_standby,
                a.remaining_minutes,
                a.run_duration_min,
                a.run_duration_max,
                a.pause_duration_min,
                a.pause_duration_max,
                a.next_start_time,
                a.usage_duration_min,
                a.usage_duration_max,
                a.weekday_hours,
                a.weekend_hours,
                a.remaining_minutes_list,
                a.planned_starts
            FROM api_house h
            JOIN api_appliance a ON (
                CASE 
                    WHEN h.id IN (999, 9999, 99999) THEN 9
                    ELSE h.id 
                END
            ) = a.house_id
            WHERE h.is_active = true
        """)
        rows = cur.fetchall()
        logger.info(f"Nalezeno {len(rows)} spotřebičů")
        
        # Pro každý dům sledujeme seznam spotřebičů a celkovou spotřebu
        houses = {}
        for (house_id, appliance_id, power, standby_power, app_type, is_active, 
             in_standby, remaining_minutes, run_duration_min, run_duration_max, 
             pause_duration_min, pause_duration_max, next_start_time,
             usage_duration_min, usage_duration_max, weekday_hours, weekend_hours,
             remaining_minutes_list, planned_starts) in rows:
            
            # Vytvoříme nový záznam pro dům pokud neexistuje
            if house_id not in houses:
                houses[house_id] = {
                    'appliances': [],  # Seznam spotřebičů
                    'total_wh': 0      # Celková spotřeba ve Wh
                }
                
            # Spočítáme spotřebu pro každý typ spotřebiče
            if app_type == 'CONSTANT':
                variation = random.uniform(0.9, 1.0)
                minute_consumption = (power * variation) / 60
                logger.debug(f"Spotřebič {appliance_id} (CONSTANT): {minute_consumption}W/min (variation: {variation:.2f})")
                
            elif app_type == 'CYCLIC':
                if remaining_minutes == 0:
                    peak_time = is_peak_time(current_time, is_weekend)
                    
                    if in_standby:
                        new_remaining = get_adjusted_duration(
                            run_duration_min,
                            run_duration_max,
                            peak_time,
                            for_active_state=True
                        )
                        cur.execute("""
                            UPDATE api_appliance 
                            SET is_active = true,
                                in_standby = false,
                                remaining_minutes = %s
                            WHERE id = %s
                        """, [new_remaining, appliance_id])
                        is_active = True
                        in_standby = False
                    else:
                        new_remaining = get_adjusted_duration(
                            pause_duration_min,
                            pause_duration_max,
                            peak_time,
                            for_active_state=False
                        )
                        cur.execute("""
                            UPDATE api_appliance 
                            SET is_active = false,
                                in_standby = true,
                                remaining_minutes = %s
                            WHERE id = %s
                        """, [new_remaining, appliance_id])
                        is_active = False
                        in_standby = True
                    
                    logger.debug(f"Spotřebič {appliance_id} změnil stav, nový čas: {new_remaining}min (špička: {peak_time})")
                    remaining_minutes = new_remaining
                
                if is_active:
                    variation = random.uniform(0.9, 1.0)
                    minute_consumption = (power * variation) / 60
                else:
                    minute_consumption = standby_power / 60
                logger.debug(f"Spotřebič {appliance_id} (CYCLIC): {minute_consumption}W/min (Active: {is_active})")
                
                if remaining_minutes > 0:
                    cur.execute("""
                        UPDATE api_appliance 
                        SET remaining_minutes = remaining_minutes - 1
                        WHERE id = %s
                    """, [appliance_id])

            elif app_type == 'SCHEDULED':
                if remaining_minutes > 0:
                    variation = random.uniform(0.9, 1.0)
                    minute_consumption = (power * variation) / 60
                    logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): {minute_consumption}W/min (Zbývá: {remaining_minutes}min)")
                    cur.execute("""
                        UPDATE api_appliance 
                        SET remaining_minutes = remaining_minutes - 1
                        WHERE id = %s
                    """, [appliance_id])
                else:
                    minute_consumption = standby_power / 60 if standby_power else 0
                    logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): {minute_consumption}W/min (Standby)")

                    if next_start_time and current_time.replace(tzinfo=None) == next_start_time.replace(tzinfo=None):
                        duration = random.randint(usage_duration_min, usage_duration_max)
                        cur.execute("""
                            UPDATE api_appliance 
                            SET remaining_minutes = %s,
                                next_start_time = NULL
                            WHERE id = %s
                        """, [duration, appliance_id])
                        logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): Spuštěn běh na {duration}min")

                if current_time.minute == 59:
                    next_hour = (current_time.hour + 1) % 24
                    windows = weekend_hours if is_weekend else weekday_hours
                    
                    if windows:
                        for window in windows:
                            if window['start'] == next_hour and random.random() < window['probability']:
                                start_minutes = window['start'] * 60
                                end_minutes = window['end'] * 60
                                if end_minutes < start_minutes:
                                    end_minutes += 24 * 60

                                if remaining_minutes > 0:
                                    earliest_start = start_minutes + remaining_minutes
                                    if earliest_start < end_minutes:
                                        random_minute = random.randint(earliest_start, end_minutes)
                                    else:
                                        continue
                                else:
                                    random_minute = random.randint(start_minutes, end_minutes)

                                target_hour = (random_minute // 60) % 24
                                target_minute = random_minute % 60
                                
                                next_start = current_time.replace(
                                    hour=target_hour,
                                    minute=target_minute
                                )

                                cur.execute("""
                                    UPDATE api_appliance 
                                    SET next_start_time = %s
                                    WHERE id = %s
                                """, [next_start, appliance_id])
                                logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): Naplánován na {next_start}")
                                break

            elif app_type == 'ON_DEMAND':
                remaining_minutes_list = [] if remaining_minutes_list is None else remaining_minutes_list
                planned_starts = [] if planned_starts is None else planned_starts

                minute_consumption = 0
                new_remaining_minutes = []
                
                for mins in remaining_minutes_list:
                    if mins > 0:
                        variation = random.uniform(0.9, 1.0)
                        minute_consumption += (power * variation) / 60
                        new_remaining_minutes.append(mins - 1)
                
                new_planned_starts = []
                current_time_str_full = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                for start in planned_starts:
                    if start == current_time_str_full:
                        duration = random.randint(usage_duration_min, usage_duration_max)
                        new_remaining_minutes.append(duration)
                        logger.debug(f"Spotřebič {appliance_id} (ON_DEMAND): Spuštěn nový běh na {duration}min")
                    else:
                        new_planned_starts.append(start)

                if current_time.minute == 59:
                    next_hour = (current_time.hour + 1) % 24
                    windows = weekend_hours if is_weekend else weekday_hours
                    
                    if windows:
                        for window in windows:
                            if window['start'] == next_hour:
                                for _ in range(window['uses']):
                                    if random.random() < window['probability']:
                                        start_minutes = window['start'] * 60
                                        end_minutes = window['end'] * 60
                                        if end_minutes < start_minutes:
                                            end_minutes += 24 * 60

                                        random_minute = random.randint(start_minutes, end_minutes)
                                        target_hour = (random_minute // 60) % 24
                                        target_minute = random_minute % 60
                                        
                                        planned_start = current_time.replace(
                                            hour=target_hour,
                                            minute=target_minute
                                        )
                                        new_planned_starts.append(planned_start.strftime('%Y-%m-%d %H:%M:%S'))
                                        logger.debug(f"Spotřebič {appliance_id} (ON_DEMAND): Naplánován start na {planned_start}")
                                break

                cur.execute("""
                    UPDATE api_appliance 
                    SET remaining_minutes_list = %s::jsonb,
                        planned_starts = %s::jsonb
                    WHERE id = %s
                """, [json.dumps(new_remaining_minutes), json.dumps(new_planned_starts), appliance_id])

            else:
                minute_consumption = 0
                logger.debug(f"Spotřebič {appliance_id}: přeskakuji (typ {app_type})")
                
            # Přidáme spotřebič do seznamu a přičteme jeho spotřebu k celkové
            houses[house_id]['appliances'].append({
                "appliance_id": appliance_id,
                "consumption_w": minute_consumption
            })
            houses[house_id]['total_wh'] += minute_consumption  # Wm = Wh/60
        
        logger.info(f"Zpracováno {len(houses)} domů")
        
        # Pro každý dům uložíme data a odečteme z baterie
        for house_id, house_data in houses.items():
            if house_data['appliances']:
                # Načteme aktuální stav baterie a účinnost vybíjení
                cur.execute("""
                    SELECT current_battery_level, discharging_efficiency
                    FROM api_house
                    WHERE id = %s
                """, [house_id])
                battery_level, efficiency = cur.fetchone()
                
                # Převedeme spotřebu na kWh a aplikujeme účinnost
                needed_kwh = (house_data['total_wh'] / 1000) / (efficiency / 100)
                
                # Vybijeme baterii
                new_level = battery_level - needed_kwh
                
                # Aktualizujeme stav baterie
                cur.execute("""
                    UPDATE api_house 
                    SET current_battery_level = %s
                    WHERE id = %s
                """, [new_level, house_id])
                
                logger.info(f"Dům {house_id}: spotřeba {house_data['total_wh']:.2f}Wh, baterie {battery_level:.2f}kWh -> {new_level:.2f}kWh")
                
                # Uložíme data o spotřebě
                cur.execute("""
                    INSERT INTO api_consumptiondata (house_id, date, time, appliance_consumption)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (house_id, date, time) 
                    DO UPDATE SET appliance_consumption = EXCLUDED.appliance_consumption
                """, (house_id, current_date, current_time_str, json.dumps(house_data['appliances'])))
        
        conn.commit()
        logger.info(f"HOTOVO! SIMULOVÁNO {len(houses)} DOMŮ V ČASE {current_date} {current_time_str}")
        
    except Exception as e:
        logger.error(f"Chyba při simulaci: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_minute_consumption()