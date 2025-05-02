import json
import psycopg2
import logging
from datetime import date, datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def get_active_houses():
    """Získá seznam ID aktivních domů, kromě domu s ID 99999"""
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id 
            FROM api_house 
            WHERE is_active = true AND id != 99999
        """)
        
        active_houses = [row[0] for row in cur.fetchall()]
        logger.info(f"Nalezeno {len(active_houses)} aktivních domů")
        
        return active_houses
        
    except Exception as e:
        logger.error(f"Chyba při načítání aktivních domů: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_price_data(current_hour, have_tomorrow_prices=False):
    """
    Získá data o cenách elektřiny s ohledem na dostupnost dat o zítřejších cenách
    
    Args:
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s informacemi o cenách pro každou hodinu v plánovacím horizontu
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)

        if have_tomorrow_prices:
            cur.execute("""
                SELECT date, hour, price_czk 
                FROM api_pricedata 
                WHERE (date = %s AND hour >= %s) OR date = %s
                ORDER BY date, hour
            """, [today, current_hour, tomorrow])
        else:
            cur.execute("""
                SELECT date, hour, price_czk 
                FROM api_pricedata 
                WHERE date = %s AND hour >= %s
                ORDER BY date, hour
            """, [today, current_hour])
        
        prices = []
        rows = cur.fetchall()
        
        for date, hour, price in rows:
            prices.append({
                'date': date,
                'hour': hour,
                'price': price / 1000,
                'index': len(prices)
            })
            
        logger.info(f"Načteno {len(rows)} cenových záznamů")
        
        if not rows:
            logger.warning("Žádné cenové záznamy nenalezeny")
        
        return prices
        
    except Exception as e:
        logger.error(f"Chyba při načítání cen: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_house_data(house_id):
    """Získá data o domu podle ID"""
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                risk_level,
                solar_power,
                battery_capacity,
                current_battery_level,
                min_battery_level,
                max_charging_power,
                charging_efficiency
            FROM api_house 
            WHERE id = %s
        """, [house_id])
        
        row = cur.fetchone()
        if row:
            house_data = {
                'risk_level': row[0],
                'solar_power': row[1],
                'battery_capacity': row[2],
                'current_battery_level': row[3],
                'min_battery_level': row[4],
                'max_charging_power': row[5],
                'charging_efficiency': row[6]
            }
            logger.info(f"Data domu {house_id} úspěšně načtena")
            return house_data
        else:
            logger.error(f"Dům {house_id} nenalezen")
            return None
        
    except Exception as e:
        logger.error(f"Chyba při načítání dat domu {house_id}: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_solar_prediction(house_power, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď solární výroby a upraví ji podle výkonu domu.
    Posunuje hodiny dozadu o 1 pro timezone kompenzaci, ale pouze pro záznamy v celou hodinu.
    
    Args:
        house_power: Výkon solárních panelů v kWp
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s predikcí solární výroby pro každou hodinu
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)
        
        solar_data = []

        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today])
        
        rows = cur.fetchall()
        logger.info(f"Načteno {len(rows)} záznamů solární výroby pro dnešek")
        
        power_ratio = house_power / 20  # Základní predikce je na 20kWp
        hour_production_today = {}
        
        for timestamp, wh in rows:
            db_hour = timestamp.hour
            
            if timestamp.minute == 0 and db_hour > 0:
                hour_production_today[db_hour - 1] = wh
            else:
                hour_production_today[db_hour] = wh
        
        if have_tomorrow_prices:
            n_hours = (24 - current_hour) + 24
        else:
            n_hours = 24 - current_hour
            
        index = 0
            
        for hour in range(current_hour, 24):
            solar_kwh = hour_production_today.get(hour, 0) * power_ratio / 1000
            
            solar_data.append({
                'date': today,
                'hour': hour,
                'solar_kwh': solar_kwh,
                'index': index
            })
            index += 1
            
        if have_tomorrow_prices:
            cur.execute("""
                SELECT timestamp, watt_hours_period
                FROM api_solardata 
                WHERE DATE(timestamp) = %s
                ORDER BY timestamp
            """, [tomorrow])
            
            tomorrow_rows = cur.fetchall()
            logger.info(f"Načteno {len(tomorrow_rows)} záznamů solární výroby pro zítřek")
            
            hour_production_tomorrow = {}
            
            for timestamp, wh in tomorrow_rows:
                db_hour = timestamp.hour
                
                if timestamp.minute == 0 and db_hour > 0:
                    hour_production_tomorrow[db_hour - 1] = wh
                else:
                    hour_production_tomorrow[db_hour] = wh
                        
            for hour in range(24):
                solar_kwh = hour_production_tomorrow.get(hour, 0) * power_ratio / 1000
                
                solar_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'solar_kwh': solar_kwh,
                    'index': index
                })
                index += 1
        
        logger.info(f"Vytvořena předpověď solární výroby pro {len(solar_data)} hodin")
        
        return solar_data
        
    except Exception as e:
        logger.error(f"Chyba při načítání solární predikce: {str(e)}")
        return []
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_consumption_prediction(house_id, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď spotřeby domu na základě historických dat
    
    Args:
        house_id: ID domu
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s predikcí spotřeby pro každou hodinu
    """
    consumption_house_id = 9 if house_id in [99, 999, 9999] else house_id
    
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)
        
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        start_date = today - timedelta(days=30)
        
        cur.execute("""
            WITH consumption_items AS (
                SELECT 
                    date,
                    time,
                    (items->>'consumption_w')::float as consumption_w
                FROM api_consumptiondata,
                LATERAL jsonb_array_elements(appliance_consumption) items
                WHERE house_id = %s 
                    AND date >= %s
            ),
            hourly_consumption AS (
                SELECT 
                    date,
                    EXTRACT(HOUR FROM time::time) as hour,
                    EXTRACT(DOW FROM date) as day_of_week,
                    SUM(consumption_w) as total_wh
                FROM consumption_items
                GROUP BY date, EXTRACT(HOUR FROM time::time)
                ORDER BY date, hour
            )
            SELECT 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END as day_type,
                AVG(total_wh) as avg_consumption
            FROM hourly_consumption
            GROUP BY 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END
            ORDER BY day_type, hour
        """, [consumption_house_id, start_date])
        
        rows = cur.fetchall()
        
        averages = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            averages[day_type][int(hour)] = avg_consumption
        
        consumption_data = []
        index = 0
        
        today_type = 'weekend' if is_today_weekend else 'weekday'
        for hour in range(current_hour, 24):
            consumption_wh = averages[today_type].get(hour, 0)
            consumption_data.append({
                'date': today,
                'hour': hour,
                'consumption_kwh': consumption_wh / 1000,  # Převod na kWh
                'index': index
            })
            index += 1
            
        if have_tomorrow_prices:
            tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
            for hour in range(24):
                consumption_wh = averages[tomorrow_type].get(hour, 0)
                consumption_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'consumption_kwh': consumption_wh / 1000,
                    'index': index
                })
                index += 1
            
        logger.info(f"Zpracováno {len(rows)} hodinových průměrů spotřeby")
        
        return consumption_data
        
    except Exception as e:
        logger.error(f"Chyba při načítání predikce spotřeby: {str(e)}")
        return []
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_consumption_prediction_by_priority(house_id, current_hour, priority_level, have_tomorrow_prices=False):
    """
    Získá předpověď spotřeby domu pro spotřebiče s určitou úrovní priority
    
    Args:
        house_id: ID domu
        current_hour: Aktuální hodina dne (0-23)
        priority_level: Úroveň priority spotřebičů (1-4)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s predikcí spotřeby pro každou hodinu
    """
    consumption_house_id = 9 if house_id in [99, 999, 9999] else house_id
    
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)
        
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        start_date = today - timedelta(days=30)
        
        cur.execute("""
            WITH consumption_items AS (
                SELECT 
                    c.date,
                    c.time,
                    (items->>'consumption_w')::float as consumption_w,
                    a.priority_level
                FROM api_consumptiondata c,
                LATERAL jsonb_array_elements(c.appliance_consumption) as items,
                api_appliance a
                WHERE c.house_id = %s 
                    AND c.date >= %s
                    AND (items->>'appliance_id')::integer = a.id
                    AND a.priority_level = %s
            ),
            hourly_consumption AS (
                SELECT 
                    date,
                    EXTRACT(HOUR FROM time::time) as hour,
                    EXTRACT(DOW FROM date) as day_of_week,
                    SUM(consumption_w) as total_wh
                FROM consumption_items
                GROUP BY date, EXTRACT(HOUR FROM time::time)
                ORDER BY date, hour
            )
            SELECT 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END as day_type,
                AVG(total_wh) as avg_consumption
            FROM hourly_consumption
            GROUP BY 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END
            ORDER BY day_type, hour
        """, [consumption_house_id, start_date, priority_level])
        
        rows = cur.fetchall()
        
        averages = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            averages[day_type][int(hour)] = avg_consumption
        
        consumption_data = []
        index = 0
        
        today_type = 'weekend' if is_today_weekend else 'weekday'
        for hour in range(current_hour, 24):
            consumption_wh = averages[today_type].get(hour, 0)
            consumption_data.append({
                'date': today,
                'hour': hour,
                'consumption_kwh': consumption_wh / 1000,  # Převod na kWh
                'index': index
            })
            index += 1
            
        if have_tomorrow_prices:
            tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
            for hour in range(24):
                consumption_wh = averages[tomorrow_type].get(hour, 0)
                consumption_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'consumption_kwh': consumption_wh / 1000,
                    'index': index
                })
                index += 1
            
        logger.info(f"Zpracovány hodinové průměry spotřeby pro prioritu {priority_level}: {len(rows)} záznamů")
        
        return consumption_data
        
    except Exception as e:
        logger.error(f"Chyba při načítání predikce spotřeby pro prioritu {priority_level}: {str(e)}")
        return []
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


def create_inactive_window_for_appliances(house_id, start_date, start_hour, end_date, end_hour, priority_level):
    """
    Vytvoří inactive_window pro spotřebiče dané priority v zadaném časovém rozmezí.
    Pro dům s ID 99 používá spotřebiče domu s ID 9.
    Zároveň maže neaktivní okna z předchozích dnů.
    
    Args:
        house_id: ID domu
        start_date: Počáteční datum (objekt date nebo string)
        start_hour: Počáteční hodina (0-23)
        end_date: Koncové datum (objekt date nebo string)
        end_hour: Koncová hodina (0-23)
        priority_level: Úroveň priority spotřebičů (1-4)
        
    Returns:
        int: Počet aktualizovaných spotřebičů
    """
    try:
        if isinstance(start_date, datetime) or isinstance(start_date, date):
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = start_date
            
        if isinstance(end_date, datetime) or isinstance(end_date, date):
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date_str = end_date
            
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        inactive_window = {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "start_hour": start_hour,
            "end_hour": end_hour
        }
        
        reference_house_id = 9 if house_id == 99 else house_id
        
        cur.execute("""
            SELECT id, appliance_type, inactive_windows 
            FROM api_appliance 
            WHERE house_id = %s 
              AND priority_level = %s
              AND appliance_type IN ('CONSTANT', 'CYCLIC')
        """, [reference_house_id, priority_level])
        
        appliances = cur.fetchall()
        
        updated_count = 0
        today = datetime.now().date()
        
        for appliance_id, appliance_type, inactive_windows in appliances:
            if inactive_windows is None:
                inactive_windows = []
            
            if inactive_windows:
                filtered_windows = []
                removed_count = 0
                
                for window in inactive_windows:
                    end_date_window = window.get("end_date", window.get("start_date", ""))
                    
                    if not end_date_window:
                        filtered_windows.append(window)
                        continue
                        
                    try:
                        end_date_obj = datetime.strptime(end_date_window, '%Y-%m-%d').date()
                        
                        if end_date_obj >= today:
                            filtered_windows.append(window)
                        else:
                            removed_count += 1
                            logger.info(f"Odstraněno staré neaktivní okno ze spotřebiče {appliance_id}")
                    except ValueError:
                        filtered_windows.append(window)
                
                inactive_windows = filtered_windows
                logger.info(f"Odstraněno {removed_count} starých oken ze spotřebiče {appliance_id}")
            
            inactive_windows.append(inactive_window)
            
            cur.execute("""
                UPDATE api_appliance 
                SET inactive_windows = %s::jsonb
                WHERE id = %s
            """, [json.dumps(inactive_windows), appliance_id])
            
            updated_count += 1
            
            logger.info(f"Pro spotřebič {appliance_id} přidáno neaktivní okno: {start_date_str} {start_hour}:00 - {end_date_str} {end_hour}:00")
        
        conn.commit()
        
        if house_id == 99:
            logger.info(f"Aktualizováno {updated_count} spotřebičů domu 9 (reference pro dům 99) s prioritou {priority_level}")
        else:
            logger.info(f"Aktualizováno {updated_count} spotřebičů s prioritou {priority_level}")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Chyba při vytváření neaktivního okna: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return 0
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


def deactivate_time_windows_for_appliances(house_id, start_date, start_hour, end_date, end_hour, priority_level):
    """
    Deaktivuje časová okna pro SCHEDULED a ON_DEMAND spotřebiče dané priority,
    která zasahují do zadaného časového intervalu.
    Pro dům s ID 99 používá spotřebiče domu s ID 9.
    
    Args:
        house_id: ID domu
        start_date: Počáteční datum (objekt date nebo string)
        start_hour: Počáteční hodina (0-23)
        end_date: Koncové datum (objekt date nebo string)
        end_hour: Koncová hodina (0-23)
        priority_level: Úroveň priority spotřebičů (1-4)
        
    Returns:
        dict: Počet aktualizovaných oken pro víkendy a všední dny
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        if isinstance(start_date, str):
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start_date_obj = start_date
            
        if isinstance(end_date, str):
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end_date_obj = end_date
            
        is_start_weekend = start_date_obj.weekday() >= 5
        is_end_weekend = end_date_obj.weekday() >= 5
        is_multiday = start_date_obj != end_date_obj
        
        logger.info(f"Deaktivace oken: {start_date_obj} - {end_date_obj}, vícedenní: {is_multiday}")

        reference_house_id = 9 if house_id == 99 else house_id

        cur.execute("""
            SELECT id, appliance_type, weekday_hours, weekend_hours 
            FROM api_appliance 
            WHERE house_id = %s 
              AND priority_level = %s
              AND appliance_type IN ('SCHEDULED', 'ON_DEMAND')
        """, [reference_house_id, priority_level])
        
        appliances = cur.fetchall()
        
        stats = {
            'weekday_windows_deactivated': 0,
            'weekend_windows_deactivated': 0,
            'appliances_affected': 0
        }
        
        def window_overlaps(window, start_h, end_h):
            window_start = window.get('start', 0)
            window_end = window.get('end', 0)
            
            if window_start > window_end:
                return (start_h <= window_end) or (window_start <= end_h)
            else:
                if start_h == end_h:
                    if window_start == window_end == start_h:
                        return True
                    return window_start <= start_h < window_end
                else:
                    return max(start_h, window_start) <= min(end_h, window_end)
        
        for appliance_id, appliance_type, weekday_hours, weekend_hours in appliances:
            appliance_updated_weekday = False
            appliance_updated_weekend = False
            
            if is_multiday or is_start_weekend:
                if weekend_hours:
                    for i, window in enumerate(weekend_hours):
                        if is_multiday:
                            if is_start_weekend and is_end_weekend:
                                overlap = window_overlaps(window, start_hour, end_hour)
                            elif is_start_weekend:
                                overlap = window_overlaps(window, start_hour, 24)
                            elif is_end_weekend:
                                overlap = window_overlaps(window, 0, end_hour)
                            else:
                                overlap = True
                        else:
                            overlap = window_overlaps(window, start_hour, end_hour)
                        
                        if window.get('is_active', True) and overlap:
                            weekend_hours[i]['is_active'] = False
                            stats['weekend_windows_deactivated'] += 1
                            appliance_updated_weekend = True
                            logger.info(f"Deaktivováno víkendové okno pro spotřebič {appliance_id}")
                
                if appliance_updated_weekend:
                    cur.execute("""
                        UPDATE api_appliance 
                        SET weekend_hours = %s::jsonb
                        WHERE id = %s
                    """, [json.dumps(weekend_hours), appliance_id])
            
            if is_multiday or not is_start_weekend:
                if weekday_hours:
                    for i, window in enumerate(weekday_hours):
                        if is_multiday:
                            if not is_start_weekend and not is_end_weekend:
                                overlap = window_overlaps(window, start_hour, end_hour)
                            elif not is_start_weekend:
                                overlap = window_overlaps(window, start_hour, 24)
                            elif not is_end_weekend:
                                overlap = window_overlaps(window, 0, end_hour)
                            else:
                                overlap = True
                        else:
                            overlap = window_overlaps(window, start_hour, end_hour)
                        
                        if window.get('is_active', True) and overlap:
                            weekday_hours[i]['is_active'] = False
                            stats['weekday_windows_deactivated'] += 1
                            appliance_updated_weekday = True
                            logger.info(f"Deaktivováno všední okno pro spotřebič {appliance_id}")
                
                if appliance_updated_weekday:
                    cur.execute("""
                        UPDATE api_appliance 
                        SET weekday_hours = %s::jsonb
                        WHERE id = %s
                    """, [json.dumps(weekday_hours), appliance_id])
            
            if appliance_updated_weekday or appliance_updated_weekend:
                stats['appliances_affected'] += 1
        
        conn.commit()
        
        logger.info(f"Deaktivováno {stats['weekday_windows_deactivated']} všedních a {stats['weekend_windows_deactivated']} víkendových oken pro {stats['appliances_affected']} spotřebičů")
        
        return stats
        
    except Exception as e:
        logger.error(f"Chyba při deaktivaci časových oken: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return {'weekday_windows_deactivated': 0, 'weekend_windows_deactivated': 0, 'appliances_affected': 0}
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_historical_price_categories(days=30):
    """
    Získá historická data o cenách a vypočítá percentilové prahy pro kategorizaci.
    
    Args:
        days: Počet dní historie pro analýzu (výchozí 30)
    
    Returns:
        Dict: Slovník s prahovými hodnotami pro jednotlivé kategorie
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        start_date = datetime.now().date() - timedelta(days=days)
        
        cur.execute("""
            SELECT price_czk 
            FROM api_pricedata 
            WHERE date >= %s
            ORDER BY price_czk
        """, [start_date])
        
        prices = [price[0] / 1000 for price in cur.fetchall()]  # Převod z Kč/MWh na Kč/kWh
        
        if not prices:
            logger.warning(f"Žádná historická data o cenách nebyla nalezena za posledních {days} dní")
            return {
                'extremely_low': 0.5,
                'low': 1.0,
                'average': 2.0,
                'high': 3.0
            }
        
        num_prices = len(prices)
        extremely_low_threshold = prices[int(num_prices * 0.1)]  # 10. percentil
        low_threshold = prices[int(num_prices * 0.25)]           # 25. percentil
        average_high_threshold = prices[int(num_prices * 0.75)]  # 75. percentil
        
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        categories = {
            'extremely_low': extremely_low_threshold,
            'low': low_threshold,
            'average': average_high_threshold,
            'high': max_price
        }
        
        logger.info(f"Kategorie cen vypočteny z {num_prices} historických záznamů:")
        logger.info(f"  - Extrémně nízké (0-10%): do {extremely_low_threshold:.3f} Kč/kWh")
        logger.info(f"  - Nízké (10-25%): {extremely_low_threshold:.3f} - {low_threshold:.3f} Kč/kWh")
        logger.info(f"  - Průměrné (25-75%): {low_threshold:.3f} - {average_high_threshold:.3f} Kč/kWh")
        logger.info(f"  - Vysoké (75-100%): nad {average_high_threshold:.3f} Kč/kWh")
        
        return categories
        
    except Exception as e:
        logger.error(f"Chyba při získávání historických kategorií cen: {str(e)}")
        return {
            'extremely_low': 0.5,
            'low': 1.0,
            'average': 2.0,
            'high': 3.0
        }
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


def categorize_price(price, categories):
    """
    Kategorizuje cenu do jedné ze čtyř kategorií.
    
    Args:
        price: Cena k kategorizaci (Kč/kWh)
        categories: Slovník s prahovými hodnotami pro kategorie
        
    Returns:
        String: Název kategorie ('extremely_low', 'low', 'average', 'high')
    """
    if price <= categories['extremely_low']:
        return 'extremely_low'
    elif price <= categories['low']:
        return 'low'
    elif price <= categories['average']:
        return 'average'
    else:
        return 'high'
    
def optimize_charging_plan(house_id, house_data, solar_data, consumption_data, price_data, have_tomorrow_prices=False):
    """
    Optimalizace nabíjení podle cenově-efektivního přístupu.
    
    Args:
        house_id: ID domu
        house_data: Objekt s parametry domu
        solar_data: Pole s predikcí solární výroby pro každou hodinu
        consumption_data: Pole s predikcí spotřeby pro každou hodinu
        price_data: Pole s cenami elektřiny pro každou hodinu
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
    
    Returns:
        Seznam s plánem nabíjení pro každou hodinu
    """
    try:
        logger.info(f"ZAČÁTEK OPTIMALIZACE NABÍJENÍ PRO DŮM {house_id}")
        
        # Získání parametrů domu
        battery_capacity = house_data['battery_capacity']
        current_battery_level = house_data['current_battery_level']
        min_battery_level_pct = house_data['min_battery_level']
        min_battery_level = battery_capacity * (min_battery_level_pct / 100)
        max_charging_power = house_data['max_charging_power']
        charging_efficiency = house_data['charging_efficiency'] / 100
        risk_level = house_data['risk_level']
        
        # Získání historických kategorií cen
        price_categories = get_historical_price_categories()
        
        # Definice cílových úrovní baterie podle rizikového profilu a kategorie ceny
        target_levels = {
            'LOW': {
                'extremely_low': 0.80,
                'low': 0.60,
                'average': 0.40,
                'high': 0.20
            },
            'MEDIUM': {
                'extremely_low': 0.70,
                'low': 0.50,
                'average': 0.30,
                'high': 0.15
            },
            'HIGH': {
                'extremely_low': 0.50,
                'low': 0.35,
                'average': 0.25,
                'high': 0.10
            },
            'EXTREME': {
                'extremely_low': 0.50,
                'low': 0.35,
                'average': 0.25,
                'high': 0.10
            }
        }
        
        target_profile = target_levels.get(risk_level, target_levels['MEDIUM'])
        n_hours = len(price_data)
        
        # Doplnění chybějících dat
        if len(solar_data) < n_hours:
            logger.warning(f"Solární data mají méně záznamů ({len(solar_data)}) než horizont plánování ({n_hours})")
            for i in range(len(solar_data), n_hours):
                solar_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'solar_kwh': 0,
                    'index': i
                })
                
        if len(consumption_data) < n_hours:
            logger.warning(f"Data spotřeby mají méně záznamů ({len(consumption_data)}) než horizont plánování ({n_hours})")
            avg_consumption = sum(item['consumption_kwh'] for item in consumption_data) / len(consumption_data) if consumption_data else 0.2
            for i in range(len(consumption_data), n_hours):
                consumption_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'consumption_kwh': avg_consumption,
                    'index': i
                })
        
        # Kategorizace cen pro každou hodinu
        for hour in price_data:
            price_category = categorize_price(hour['price'], price_categories)
            hour['price_category'] = price_category
            
            base_target_percentage = target_profile[price_category]
            hour['base_target_level'] = battery_capacity * base_target_percentage
            hour['base_target_percentage'] = base_target_percentage * 100
            
            target_with_reserve_percentage = base_target_percentage * 1.1
            hour['target_level'] = battery_capacity * target_with_reserve_percentage
            hour['target_percentage'] = target_with_reserve_percentage * 100
        
        logger.info(f"Rizikový profil: {risk_level}")
        
        # Seřazení hodin podle ceny
        sorted_price_indices = sorted(range(n_hours), key=lambda i: price_data[i]['price'])
        
        # Simulace baterie
        def simulate_battery_levels(charging_plan, overcharge_start_idx=None):
            levels = []
            current_level = current_battery_level
            
            for i in range(n_hours):
                solar = solar_data[i]['solar_kwh'] if i < len(solar_data) else 0
                consumption = consumption_data[i]['consumption_kwh'] if i < len(consumption_data) else 0
                charging_grid = charging_plan[i] if i < len(charging_plan) else 0
                
                effective_solar = solar * charging_efficiency
                effective_grid_charging = charging_grid * charging_efficiency
                
                net_flow = effective_solar - consumption + effective_grid_charging
                
                if overcharge_start_idx is not None and i >= overcharge_start_idx:
                    current_level = max(0, current_level + net_flow)
                else:
                    current_level = max(0, min(battery_capacity, current_level + net_flow))
                
                levels.append({
                    'hour': price_data[i]['hour'],
                    'date': price_data[i]['date'],
                    'level': current_level,
                    'net_flow': net_flow,
                    'solar': solar,
                    'effective_solar': effective_solar,
                    'consumption': consumption,
                    'charging_grid': charging_grid,
                    'effective_grid_charging': effective_grid_charging,
                    'price': price_data[i]['price'],
                    'price_category': price_data[i]['price_category'],
                    'base_target_level': price_data[i]['base_target_level'],
                    'target_level': price_data[i]['target_level'],
                    'index': i
                })
                
            return levels
        
        # Inicializace plánu a počáteční simulace
        charging_plan = [0] * n_hours
        initial_levels = simulate_battery_levels(charging_plan)
        
        # Nastavení minimální požadované úrovně baterie
        high_category = "high"
        high_target_level = battery_capacity * target_profile[high_category]
        high_target_with_reserve = high_target_level * 1.1
        
        logger.info(f"=== ŘEŠENÍ KRITICKÝCH HODIN ===")
        
        # Řešení kritických hodin
        for hour_idx in range(n_hours):
            current_levels = simulate_battery_levels(charging_plan)
            current_level = current_levels[hour_idx]['level']
            
            if current_level < high_target_level:
                target_hour = current_levels[hour_idx]
                energy_deficit = (high_target_level * 1.10) - current_level
                logger.info(f"KRITICKÁ HODINA NALEZENA: {target_hour['date']} {target_hour['hour']}:00")
                
                remaining_deficit = energy_deficit / charging_efficiency
                high_price_hour_handled = False
                
                previous_hours_indices = list(range(hour_idx + 1))
                previous_hours_sorted = sorted(previous_hours_indices, key=lambda idx: price_data[idx]['price'])
                
                for prev_idx in previous_hours_sorted:
                    if remaining_deficit <= 0.01:
                        break
                    
                    prev_hour = price_data[prev_idx]
                    
                    # Speciální zpracování pro EXTREME režim
                    if risk_level == 'EXTREME' and prev_hour['price_category'] == 'high' and not high_price_hour_handled:
                        high_price_hour_handled = True
                        
                        critical_hour_date = target_hour['date']
                        critical_hour = target_hour['hour']
                        
                        for priority_level in [4, 3, 2]:
                            if remaining_deficit <= 0.01:
                                break
                                
                            priority_consumption = get_consumption_prediction_by_priority(
                                house_id, 
                                current_hour=price_data[hour_idx]['hour'],
                                priority_level=priority_level,
                                have_tomorrow_prices=have_tomorrow_prices
                            )
                            
                            original_consumption = consumption_data.copy()
                            
                            max_hours_back = 5
                            hours_to_check = min(hour_idx, max_hours_back)
                            start_idx = max(0, hour_idx - hours_to_check)
                            
                            potential_savings = 0
                            deactivation_hours = []
                            
                            for i in range(start_idx, hour_idx + 1):
                                hour_data = current_levels[i]
                                
                                for p_item in priority_consumption:
                                    if p_item['date'] == hour_data['date'] and p_item['hour'] == hour_data['hour']:
                                        potential_savings += p_item['consumption_kwh']
                                        
                                        deactivation_hours.append({
                                            'date': p_item['date'],
                                            'hour': p_item['hour'],
                                            'savings': p_item['consumption_kwh']
                                        })
                                        
                                        for j, cons_item in enumerate(consumption_data):
                                            if cons_item['date'] == p_item['date'] and cons_item['hour'] == p_item['hour']:
                                                consumption_data[j]['consumption_kwh'] -= p_item['consumption_kwh']
                                                break
                                                
                                        break
                            
                            if potential_savings > 0:
                                test_levels = simulate_battery_levels(charging_plan)
                                new_level = test_levels[hour_idx]['level']
                                
                                deficit_resolved = max(0, new_level - current_level)
                                remaining_deficit -= deficit_resolved
                                
                                if deficit_resolved > 0:
                                    for deact_hour in deactivation_hours:
                                        hour_date = deact_hour['date']
                                        hour_hour = deact_hour['hour']
                                        
                                        if critical_hour == hour_hour:
                                            end_hour = hour_hour + 1
                                            if end_hour > 23:
                                                end_hour = 23
                                        else:
                                            end_hour = critical_hour
                                            
                                        create_inactive_window_for_appliances(
                                            house_id=house_id,
                                            start_date=hour_date,
                                            start_hour=hour_hour,
                                            end_date=critical_hour_date,
                                            end_hour=end_hour,
                                            priority_level=priority_level
                                        )
                                        
                                        deactivate_time_windows_for_appliances(
                                            house_id=house_id,
                                            start_date=hour_date,
                                            start_hour=hour_hour,
                                            end_date=critical_hour_date,
                                            end_hour=end_hour,
                                            priority_level=priority_level
                                        )
                                else:
                                    consumption_data = original_consumption
                    
                    # Standardní nabíjení ze sítě
                    solar_hour = next((s for s in solar_data if s['hour'] == prev_hour['hour'] and s['date'] == prev_hour['date']), None)
                    solar_production = solar_hour['solar_kwh'] if solar_hour else 0
                    
                    available_charging_power = max(0, max_charging_power - solar_production)
                    current_charging = charging_plan[prev_idx]
                    additional_charging_possible = max(0, available_charging_power - current_charging)
                    
                    if additional_charging_possible <= 0:
                        continue
                    
                    energy_to_add = min(remaining_deficit, additional_charging_possible)
                    
                    test_plan = charging_plan.copy()
                    test_plan[prev_idx] += energy_to_add
                    
                    test_levels = simulate_battery_levels(test_plan)
                    new_level = test_levels[hour_idx]['level']
                    
                    effective_energy_added = max(0, new_level - current_level)
                    effective_deficit_reduction = min(energy_deficit, effective_energy_added)
                    
                    energy_utilization_ratio = effective_deficit_reduction / (energy_to_add * charging_efficiency) if energy_to_add > 0 else 0
                    
                    if effective_deficit_reduction > 0:
                        actual_energy_to_add = energy_to_add
                        
                        if energy_utilization_ratio < 0.99:
                            actual_energy_to_add = (effective_deficit_reduction / charging_efficiency)
                        
                        charging_plan[prev_idx] += actual_energy_to_add
                        remaining_deficit -= actual_energy_to_add
                
                current_levels = simulate_battery_levels(charging_plan)
                current_level = current_levels[hour_idx]['level']
                
                if current_level < high_target_with_reserve:
                    logger.warning(f"NEPODAŘILO SE ZCELA VYŘEŠIT KRITICKOU HODINU: Stav baterie {current_level:.2f} kWh < {high_target_with_reserve:.2f} kWh")
        
        logger.info(f"=== STANDARDNÍ OPTIMALIZACE PRO KONCOVÝ CÍL ===")
        
        # Standardní optimalizace pro koncový cíl
        for hour_idx in sorted_price_indices:
            current_hour = price_data[hour_idx]
            base_target = current_hour['base_target_level']
            hour_target = current_hour['target_level']
            
            current_levels = simulate_battery_levels(charging_plan)
            end_level = current_levels[-1]['level']
            
            if end_level < base_target:
                solar_hour = next((s for s in solar_data if s['hour'] == current_hour['hour'] and s['date'] == current_hour['date']), None)
                solar_production = solar_hour['solar_kwh'] if solar_hour else 0
                
                available_charging_power = max(0, max_charging_power - solar_production)
                current_planned_charging = charging_plan[hour_idx]
                additional_charging_possible = max(0, available_charging_power - current_planned_charging)
                
                if additional_charging_possible <= 0:
                    continue
                
                test_charging_plan = charging_plan.copy()
                test_charging_plan[hour_idx] = available_charging_power
                test_levels = simulate_battery_levels(test_charging_plan, hour_idx)
                
                max_level = 0
                max_level_hour = None
                capacity_excess = 0
                
                for i, level in enumerate(test_levels[hour_idx:], hour_idx):
                    if level['level'] > max_level:
                        max_level = level['level']
                        max_level_hour = level['hour']
                        
                if max_level > battery_capacity * 0.999:
                    capacity_excess = max_level - battery_capacity
                
                end_test_level = test_levels[-1]['level']
                target_excess = 0
                
                if end_test_level > hour_target:
                    target_excess = end_test_level - hour_target
                
                energy_excess = max(capacity_excess, target_excess)
                additional_charging = additional_charging_possible
                
                if energy_excess > 0:
                    excess_charging = energy_excess / charging_efficiency
                    additional_charging = max(0, additional_charging_possible - excess_charging)
                
                charging_plan[hour_idx] = current_planned_charging + additional_charging
        
        # Finalizace plánu
        final_levels = simulate_battery_levels(charging_plan)
        
        # Kontrola kritických hodin po optimalizaci
        logger.info(f"=== KONTROLA KRITICKÝCH HODIN PO OPTIMALIZACI ===")
        critical_hours_after = []
        
        for i, level in enumerate(final_levels):
            if level['level'] < high_target_level:
                energy_deficit = high_target_with_reserve - level['level']
                critical_hours_after.append({
                    'index': i,
                    'hour': level['hour'],
                    'date': level['date'],
                    'level': level['level'],
                    'target': high_target_with_reserve,
                    'deficit': energy_deficit,
                    'deficit_with_efficiency': energy_deficit / charging_efficiency
                })
                
                logger.warning(f"PŘETRVÁVAJÍCÍ KRITICKÁ HODINA: {level['date']} {level['hour']}:00 - Stav baterie: {level['level']:.2f} kWh, Deficit: {energy_deficit:.2f} kWh")
        
        # Vytvoření finálního plánu
        final_plan = []
        for i in range(n_hours):
            level = final_levels[i]
            plan = {
                'hour': level['hour'],
                'date': level['date'],
                'planned_charging_kwh': charging_plan[i],
                'battery_level': level['level'],
                'battery_percent': level['level'] / battery_capacity * 100,
                'price': level['price'],
                'price_category': level['price_category'],
                'base_target_level': level['base_target_level'],
                'base_target_percent': level['base_target_level'] / battery_capacity * 100,
                'target_level': level['target_level'],
                'target_percent': level['target_level'] / battery_capacity * 100,
                'solar_production': level['solar'],
                'consumption': level['consumption']
            }
            final_plan.append(plan)
        
        # Výpočet celkových nákladů
        total_energy = sum(plan['planned_charging_kwh'] for plan in final_plan)
        total_cost = sum(plan['planned_charging_kwh'] * plan['price'] for plan in final_plan)
        
        logger.info(f"Celkové nabíjení: {total_energy:.2f} kWh")
        logger.info(f"Celkové náklady: {total_cost:.2f} Kč")
        
        return final_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI OPTIMALIZACI NABÍJENÍ: {str(e)}", exc_info=True)
        return []
    
def save_charging_schedule(house_id, charging_plan):
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM api_chargingschedule
            WHERE house_id = %s
        """, [house_id])
        
        saved_count = 0
        MIN_CHARGING_THRESHOLD = 0.01
        
        for plan_item in charging_plan:
            hour = plan_item['hour']
            amount = plan_item['planned_charging_kwh']
            date = plan_item['date']
            
            if amount < MIN_CHARGING_THRESHOLD:
                continue
            
            cur.execute("""
                INSERT INTO api_chargingschedule
                (house_id, date, hour, planned_charging_kwh)
                VALUES (%s, %s, %s, %s)
            """, [
                house_id,
                date,
                hour,
                amount
            ])
            saved_count += 1
        
        conn.commit()
        logger.info(f"ULOŽEN PLÁN NABÍJENÍ: {saved_count} záznamů pro dům {house_id}")
        
    except Exception as e:
        logger.error(f"CHYBA PŘI UKLÁDÁNÍ PLÁNU NABÍJENÍ: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def plan_charging_for_house(house_id):
    try:
        logger.info(f"ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        
        current_time = datetime.now()
        next_hour = current_time.hour + 1
        current_date = current_time.date()
        tomorrow = current_date + timedelta(days=1)
        
        have_tomorrow_prices = next_hour >= 17
        
        if have_tomorrow_prices:
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {tomorrow.strftime('%Y-%m-%d')} 23:59"
        else:
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {current_date.strftime('%Y-%m-%d')} 23:59"
        
        logger.info(f"Plánovací horizont: {planning_horizon}")
        
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} nenalezen")
            return False
        
        price_data = get_price_data(
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        if not price_data:
            logger.error("PLÁNOVÁNÍ NABÍJENÍ: Žádná data o cenách elektřiny nebyla nalezena")
            return False
            
        solar_data = get_solar_prediction(
            house_power=house_data['solar_power'],
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        consumption_data = get_consumption_prediction(
            house_id, 
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        charging_plan = optimize_charging_plan(
            house_id,
            house_data,
            solar_data,
            consumption_data,
            price_data,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        save_charging_schedule(house_id, charging_plan)
        
        logger.info(f"KONEC PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}: {str(e)}")
        return False
    
if __name__ == "__main__":
    try:
        logger.info("================================")
        logger.info("ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ")
        logger.info("================================")
        
        active_houses = get_active_houses()
        logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Zpracovávám {len(active_houses)} aktivních domů")
        
        for house_id in active_houses:
            logger.info(f"------------------------------------")
            logger.info(f"ZAHAJUJI PLÁNOVÁNÍ PRO DŮM {house_id}")
            logger.info(f"------------------------------------")
            
            result = plan_charging_for_house(house_id)
            status = "úspěšně" if result else "neúspěšně"
            logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} zpracován {status}")
            logger.info(f"------------------------------------")
        
        logger.info("================================")
        logger.info("KONEC PLÁNOVÁNÍ NABÍJENÍ")
        logger.info("================================")
        
    except Exception as e:
        logger.error(f"KRITICKÁ CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ: {str(e)}")
        logger.error(f"STACKTRACE: ", exc_info=True)