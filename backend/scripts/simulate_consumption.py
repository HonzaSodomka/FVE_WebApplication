import psycopg2
from datetime import datetime
import logging
import json
import random

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger('api')

def simulate_minute_consumption():
    try:
        print("Začínám simulaci")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        print("Připojeno k databázi")
        cur = conn.cursor()

        current_time = datetime.now().replace(second=0, microsecond=0)
        is_weekend = current_time.weekday() >= 5
        print(f"Simuluji pro čas: {current_time} ({'víkend' if is_weekend else 'pracovní den'})")
        
        cur.execute("""
            SELECT 
                h.id as house_id,
                a.id as appliance_id,
                a.power_consumption,
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
            JOIN api_appliance a ON h.id = a.house_id
        """)
        rows = cur.fetchall()
        print(f"Nalezeno {len(rows)} spotřebičů")
        
        houses = {}
        for (house_id, appliance_id, power, app_type, is_active, in_standby, 
             remaining_minutes, run_duration_min, run_duration_max, 
             pause_duration_min, pause_duration_max, next_start_time,
             usage_duration_min, usage_duration_max, weekday_hours, weekend_hours,
             remaining_minutes_list, planned_starts) in rows:
            if house_id not in houses:
                houses[house_id] = []
                
            if app_type == 'CONSTANT':
                minute_consumption = power / 60
                print(f"Spotřebič {appliance_id} (CONSTANT): {minute_consumption}W/min")
                
            elif app_type == 'CYCLIC':
                # NEJDŘÍV kontrola a změna stavu pokud je potřeba
                if remaining_minutes == 0:
                    if in_standby:
                        new_remaining = random.randint(run_duration_min, run_duration_max)
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
                        new_remaining = random.randint(pause_duration_min, pause_duration_max)
                        cur.execute("""
                            UPDATE api_appliance 
                            SET is_active = false,
                                in_standby = true,
                                remaining_minutes = %s
                            WHERE id = %s
                        """, [new_remaining, appliance_id])
                        is_active = False
                        in_standby = True
                    
                    print(f"Spotřebič {appliance_id} změnil stav, nový čas: {new_remaining}min")
                    remaining_minutes = new_remaining
                
                if is_active:
                    minute_consumption = power / 60
                else:
                    minute_consumption = (power * 0.1) / 60
                print(f"Spotřebič {appliance_id} (CYCLIC): {minute_consumption}W/min (Active: {is_active})")
                
                if remaining_minutes > 0:
                    cur.execute("""
                        UPDATE api_appliance 
                        SET remaining_minutes = remaining_minutes - 1
                        WHERE id = %s
                    """, [appliance_id])

            elif app_type == 'SCHEDULED':
                if remaining_minutes > 0:
                    minute_consumption = power / 60
                    print(f"Spotřebič {appliance_id} (SCHEDULED): {minute_consumption}W/min (Zbývá: {remaining_minutes}min)")
                    cur.execute("""
                        UPDATE api_appliance 
                        SET remaining_minutes = remaining_minutes - 1
                        WHERE id = %s
                    """, [appliance_id])
                else:
                    if next_start_time and current_time == next_start_time:
                        duration = random.randint(usage_duration_min, usage_duration_max)
                        cur.execute("""
                            UPDATE api_appliance 
                            SET remaining_minutes = %s,
                                next_start_time = NULL
                            WHERE id = %s
                        """, [duration, appliance_id])
                        minute_consumption = 0
                        print(f"Spotřebič {appliance_id} (SCHEDULED): Naplánován běh na {duration}min")
                    else:
                        minute_consumption = 0
                        if current_time.minute == 59:
                            next_hour = (current_time.hour + 1) % 24
                            windows = weekend_hours if is_weekend else weekday_hours
                            
                            if windows:
                                for window in windows:
                                    if window['start'] == next_hour:
                                        if random.random() < window['probability']:
                                            start_minutes = window['start'] * 60
                                            end_minutes = window['end'] * 60
                                            if end_minutes < start_minutes:
                                                end_minutes += 24 * 60

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
                                            print(f"Spotřebič {appliance_id} (SCHEDULED): Naplánován na {next_start}")
                                        break

            elif app_type == 'ON_DEMAND':
                # Inicializace seznamů pokud neexistují
                if not remaining_minutes_list:
                    remaining_minutes_list = []
                if not planned_starts:
                    planned_starts = []

                # Kontrola běžících spotřeb a jejich aktualizace
                minute_consumption = 0
                new_remaining_minutes = []
                
                for mins in remaining_minutes_list:
                    if mins > 0:
                        minute_consumption += power / 60
                        new_remaining_minutes.append(mins - 1)
                    
                # Kontrola naplánovaných startů
                new_planned_starts = []
                current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                for start in planned_starts:
                    if start == current_time_str:
                        # Spustíme nový běh
                        duration = random.randint(usage_duration_min, usage_duration_max)
                        new_remaining_minutes.append(duration)
                        print(f"Spotřebič {appliance_id} (ON_DEMAND): Spuštěn nový běh na {duration}min")
                    else:
                        new_planned_starts.append(start)

                # Plánování nových startů v časových oknech
                if current_time.minute == 59:
                    next_hour = (current_time.hour + 1) % 24
                    windows = weekend_hours if is_weekend else weekday_hours
                    
                    if windows:
                        for window in windows:
                            if window['start'] == next_hour:
                                # Pro každé použití v okně
                                for _ in range(window['uses']):
                                    if random.random() < window['probability']:
                                        # Výběr náhodného času v okně
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
                                        print(f"Spotřebič {appliance_id} (ON_DEMAND): Naplánován start na {planned_start}")
                                break

                # Aktualizace seznamů v databázi
                cur.execute("""
                    UPDATE api_appliance 
                    SET remaining_minutes_list = %s,
                        planned_starts = %s
                    WHERE id = %s
                """, [new_remaining_minutes, new_planned_starts, appliance_id])

            else:
                minute_consumption = 0
                print(f"Spotřebič {appliance_id}: přeskakuji (typ {app_type})")
                
            houses[house_id].append({
                "appliance_id": appliance_id,
                "consumption_w": minute_consumption
            })
        
        print(f"Zpracováno {len(houses)} domů")
        
        for house_id, appliances in houses.items():
            if appliances:
                print(f"Ukládám data pro dům {house_id}: {json.dumps(appliances)}")
                cur.execute("""
                    INSERT INTO api_consumptiondata (house_id, timestamp, appliance_consumption)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (house_id, timestamp) 
                    DO UPDATE SET appliance_consumption = EXCLUDED.appliance_consumption
                """, (house_id, current_time, json.dumps(appliances)))
        
        conn.commit()
        print(f"Hotovo! Simulováno {len(houses)} domů v čase {current_time}")
        
    except Exception as e:
        print(f"Chyba: {str(e)}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    simulate_minute_consumption()