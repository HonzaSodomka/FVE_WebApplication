import json
import psycopg2
import logging
from datetime import datetime, timedelta

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
        logger.info(f"NAČÍTÁNÍ AKTIVNÍCH DOMŮ: Nalezeno {len(active_houses)} domů")
        
        return active_houses
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ AKTIVNÍCH DOMŮ: {str(e)}")
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

        # Upravíme dotaz podle dostupnosti dat o zítřejších cenách
        if have_tomorrow_prices:
            # Máme data na zítřek, načteme hodiny od aktuální až do konce zítřka
            cur.execute("""
                SELECT date, hour, price_czk 
                FROM api_pricedata 
                WHERE (date = %s AND hour >= %s) OR date = %s
                ORDER BY date, hour
            """, [today, current_hour, tomorrow])
        else:
            # Nemáme data na zítřek, načteme jen hodiny od aktuální do konce dneška
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
                'price': price / 1000,  # Převod z Kč/MWh na Kč/kWh
                'index': len(prices)     # Index v plánovacím horizontu
            })
            
        logger.info(f"NAČÍTÁNÍ CEN: Načteno {len(rows)} cenových záznamů")
        
        if not rows:
            logger.warning("NAČÍTÁNÍ CEN: Žádné cenové záznamy nenalezeny")
        
        return prices
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ CEN: {str(e)}")
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
            logger.info(f"NAČÍTÁNÍ DAT DOMU {house_id}: Data úspěšně načtena")
            return house_data
        else:
            logger.error(f"NAČÍTÁNÍ DAT DOMU {house_id}: Dům nenalezen")
            return None
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ DAT DOMU {house_id}: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_solar_prediction(house_power, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď solární výroby a upraví ji podle výkonu domu.
    Posunuje hodiny dozadu o 1, ale pouze pro záznamy v celou hodinu.
    Záznamy s minutami (např. 17:45) zůstanou v původní hodině.
    
    Args:
        house_power: Výkon solárních panelů v kWp
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s predikcí solární výroby pro každou hodinu v plánovacím horizontu
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

        # Načteme všechna data solární produkce pro dnešek
        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today])
        
        rows = cur.fetchall()
        logger.info(f"Načteno {len(rows)} záznamů predikce solární výroby pro dnešek")
        
        # Přepočítací faktory
        power_ratio = house_power / 20  # Základní predikce je na 20kWp
        
        # Vytvoříme slovník s produkcí dle hodin pro dnešek s posunem o 1 hodinu zpět
        hour_production_today = {}
        
        for timestamp, wh in rows:
            db_hour = timestamp.hour
            
            # Posunujeme pouze záznamy v celou hodinu (minute == 0)
            if timestamp.minute == 0 and db_hour > 0:
                # Posun o 1 hodinu zpět pro záznamy v celou hodinu
                hour_production_today[db_hour - 1] = wh
            else:
                # Záznamy s minutami (např. 17:45) zůstanou v původní hodině
                hour_production_today[db_hour] = wh
        
        # Vytvoříme pole solární produkce pro všechny hodiny v plánovacím horizontu
        if have_tomorrow_prices:
            # Máme data na zítřek, plánujeme od current_hour do 23 hodin následujícího dne
            n_hours = (24 - current_hour) + 24
        else:
            # Nemáme data na zítřek, plánujeme od current_hour do 23 hodin dnes
            n_hours = 24 - current_hour
            
        # Pro indexování v plánovacím horizontu
        index = 0
            
        # Plnění dat pro dnešek
        for hour in range(current_hour, 24):
            solar_kwh = hour_production_today.get(hour, 0) * power_ratio / 1000
            
            solar_data.append({
                'date': today,
                'hour': hour,
                'solar_kwh': solar_kwh,
                'index': index
            })
            index += 1
            
        # Plnění dat pro zítřek (pokud máme ceny)
        if have_tomorrow_prices:
            # Pokud máme data na zítřek, musíme je také načíst
            cur.execute("""
                SELECT timestamp, watt_hours_period
                FROM api_solardata 
                WHERE DATE(timestamp) = %s
                ORDER BY timestamp
            """, [tomorrow])
            
            tomorrow_rows = cur.fetchall()
            logger.info(f"Načteno {len(tomorrow_rows)} záznamů predikce solární výroby pro zítřek")
            
            # Vytvoříme slovník s produkcí dle hodin pro zítřek s posunem o 1 hodinu zpět
            hour_production_tomorrow = {}
            
            for timestamp, wh in tomorrow_rows:
                db_hour = timestamp.hour
                
                # Posunujeme pouze záznamy v celou hodinu (minute == 0)
                if timestamp.minute == 0 and db_hour > 0:
                    # Posun o 1 hodinu zpět pro záznamy v celou hodinu
                    hour_production_tomorrow[db_hour - 1] = wh
                else:
                    # Záznamy s minutami (např. 17:45) zůstanou v původní hodině
                    hour_production_tomorrow[db_hour] = wh
                        
            # Plnění dat pro zítřek
            for hour in range(24):
                solar_kwh = hour_production_tomorrow.get(hour, 0) * power_ratio / 1000
                
                solar_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'solar_kwh': solar_kwh,
                    'index': index
                })
                index += 1
        
        logger.info(f"NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Vytvořena předpověď pro {len(solar_data)} hodin s posunem pouze pro celé hodiny")
        
        return solar_data
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: {str(e)}")
        # V případě chyby, vracíme prázdné pole
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
        Seznam objektů s predikcí spotřeby pro každou hodinu v plánovacím horizontu
    """
    # Pokud je dům s ID 999 nebo 9999, použij data z domu s ID 9
    consumption_house_id = 9 if house_id in [999, 9999] else house_id
    
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
        
        # Zjistíme typ dnů (víkend/všední)
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        # Načteme historická data za posledních 30 dní
        start_date = today - timedelta(days=30)
        
        # SQL dotaz pro získání průměrných hodinových spotřeb podle typu dne
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
        """, [consumption_house_id, start_date])  # Zde použijeme upravené ID domu
        
        rows = cur.fetchall()
        
        # Průměrná spotřeba podle typů dnů
        averages = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            averages[day_type][int(hour)] = avg_consumption
        
        # Vytvoříme pole se spotřebami po hodinách
        consumption_data = []
        index = 0
        
        # Pro dnešek od aktuální hodiny
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
            
        # Pro zítřek všechny hodiny, jen pokud máme ceny na zítřek
        if have_tomorrow_prices:
            tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
            for hour in range(24):
                consumption_wh = averages[tomorrow_type].get(hour, 0)
                consumption_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'consumption_kwh': consumption_wh / 1000,  # Převod na kWh
                    'index': index
                })
                index += 1
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return consumption_data
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        # V případě chyby, vracíme prázdné pole
        return []
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_potential_savings(house_id, priority_level, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď potenciálních úspor vypnutím spotřebičů s danou prioritou.
    
    Args:
        house_id: ID domu
        priority_level: Úroveň priority spotřebičů (2, 3 nebo 4)
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s potenciálními úsporami pro každou hodinu v plánovacím horizontu
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
        
        # Získáme údaje o spotřebičích daného domu s danou prioritou
        cur.execute("""
            SELECT 
                id, power_consumption, appliance_type, standby_power
            FROM api_appliance 
            WHERE house_id = %s 
                AND priority_level = %s 
                AND appliance_type IN ('CONSTANT', 'CYCLIC')
        """, [house_id, priority_level])
        
        appliances = cur.fetchall()
        
        if not appliances:
            return []
        
        # Vytvoříme pole s potenciálními úsporami po hodinách
        savings_data = []
        index = 0
        
        # Pro dnešek od aktuální hodiny
        for hour in range(current_hour, 24):
            savings_kwh = 0
            
            for appliance_id, power, app_type, standby in appliances:
                if app_type == 'CONSTANT':
                    # Pro konstantní spotřebiče jednoduše vezmeme jejich spotřebu
                    savings_kwh += power / 1000  # Převod na kWh
                elif app_type == 'CYCLIC':
                    # Pro cyklické spotřebiče 50% času aktivní a 50% standby (zjednodušení)
                    standby_power = standby if standby else 0
                    avg_power = (power * 0.5 + standby_power * 0.5) / 1000  # Převod na kWh
                    savings_kwh += avg_power
            
            savings_data.append({
                'date': today,
                'hour': hour,
                'savings_kwh': savings_kwh,
                'index': index
            })
            index += 1
            
        # Pro zítřek všechny hodiny, jen pokud máme ceny na zítřek
        if have_tomorrow_prices:
            for hour in range(24):
                savings_kwh = 0
                
                for appliance_id, power, app_type, standby in appliances:
                    if app_type == 'CONSTANT':
                        savings_kwh += power / 1000
                    elif app_type == 'CYCLIC':
                        standby_power = standby if standby else 0
                        avg_power = (power * 0.5 + standby_power * 0.5) / 1000
                        savings_kwh += avg_power
                
                savings_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'savings_kwh': savings_kwh,
                    'index': index
                })
                index += 1
        
        return savings_data
        
    except Exception as e:
        logger.error(f"Chyba při získávání potenciálních úspor: {str(e)}")
        return []
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def window_overlaps(time_window, start_hour, end_hour):
    """
    Kontroluje, zda se časové okno překrývá s neaktivním oknem.
    
    Args:
        time_window: Časové okno z weekday_hours nebo weekend_hours
        start_hour: Počáteční hodina neaktivního okna
        end_hour: Koncová hodina neaktivního okna
        
    Returns:
        Boolean: True pokud se okna překrývají
    """
    window_start = time_window['start']
    window_end = time_window['end']
    
    # Speciální zpracování pro okna přes půlnoc
    if window_end < window_start:
        window_end += 24
    if end_hour < start_hour:
        end_hour += 24
    
    # Kontrola překrytí (aspoň částečné)
    return not (window_end <= start_hour or window_start >= end_hour)
    
def apply_inactive_window(house_id, priority_level, inactive_window):
    """
    Aplikuje neaktivní okno na všechny spotřebiče dané priority v domě.
    
    Args:
        house_id: ID domu
        priority_level: Úroveň priority spotřebičů (2, 3 nebo 4)
        inactive_window: Slovník s definicí časového okna 
                        {'start_date', 'end_date', 'start_hour', 'end_hour'}
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        # Získáme všechny spotřebiče dané priority
        cur.execute("""
            SELECT 
                id, appliance_type, inactive_windows, weekday_hours, weekend_hours
            FROM api_appliance 
            WHERE house_id = %s 
                AND priority_level = %s
        """, [house_id, priority_level])
        
        appliances = cur.fetchall()
        
        if not appliances:
            logger.info(f"Žádné spotřebiče s prioritou {priority_level} nebyly nalezeny v domě {house_id}")
            return
        
        updated_constant_cyclic = 0
        updated_scheduled_ondemand = 0
        
        # Převedeme časové okno na date objekty pro kontrolu, zda jde o víkend nebo pracovní den
        start_date = datetime.strptime(inactive_window['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(inactive_window['end_date'], '%Y-%m-%d').date()
        start_hour = inactive_window['start_hour']
        end_hour = inactive_window['end_hour']
        
        # Určíme, zda jde o víkend nebo pracovní den
        is_start_weekend = start_date.weekday() >= 5  # 5 = sobota, 6 = neděle
        is_end_weekend = end_date.weekday() >= 5
        
        # Pro každý spotřebič aplikujeme neaktivní okno podle typu
        for appliance_id, app_type, current_windows, weekday_hours, weekend_hours in appliances:
            if app_type in ['CONSTANT', 'CYCLIC']:
                # Pro konstantní a cyklické spotřebiče přidáme nové inactive_window
                if current_windows is None:
                    current_windows = []
                
                # Přidáme nové okno
                current_windows.append(inactive_window)
                
                # Aktualizujeme spotřebič
                cur.execute("""
                    UPDATE api_appliance
                    SET inactive_windows = %s
                    WHERE id = %s
                """, [json.dumps(current_windows), appliance_id])
                
                updated_constant_cyclic += 1
                
            elif app_type in ['SCHEDULED', 'ON_DEMAND']:
                # Pro plánované a on-demand spotřebiče deaktivujeme existující časová okna
                weekday_updated = False
                weekend_updated = False
                
                # Zpracování pro pracovní dny
                if weekday_hours and (not is_start_weekend or not is_end_weekend):
                    modified_weekday_hours = weekday_hours.copy()
                    for i, window in enumerate(modified_weekday_hours):
                        # Kontrola, zda okno překrývá neaktivní okno
                        if window_overlaps(window, start_hour, end_hour):
                            modified_weekday_hours[i]['is_active'] = False
                            weekday_updated = True
                    
                    if weekday_updated:
                        cur.execute("""
                            UPDATE api_appliance
                            SET weekday_hours = %s
                            WHERE id = %s
                        """, [json.dumps(modified_weekday_hours), appliance_id])
                
                # Zpracování pro víkendy
                if weekend_hours and (is_start_weekend or is_end_weekend):
                    modified_weekend_hours = weekend_hours.copy()
                    for i, window in enumerate(modified_weekend_hours):
                        # Kontrola, zda okno překrývá neaktivní okno
                        if window_overlaps(window, start_hour, end_hour):
                            modified_weekend_hours[i]['is_active'] = False
                            weekend_updated = True
                    
                    if weekend_updated:
                        cur.execute("""
                            UPDATE api_appliance
                            SET weekend_hours = %s
                            WHERE id = %s
                        """, [json.dumps(modified_weekend_hours), appliance_id])
                
                if weekday_updated or weekend_updated:
                    updated_scheduled_ondemand += 1
        
        conn.commit()
        logger.info(f"Úspěšně aplikováno neaktivní okno:")
        logger.info(f"- {updated_constant_cyclic} spotřebičů typu CONSTANT/CYCLIC")
        logger.info(f"- {updated_scheduled_ondemand} spotřebičů typu SCHEDULED/ON_DEMAND")
        
    except Exception as e:
        logger.error(f"Chyba při aplikování neaktivního okna: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
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
        
        # Získání dat za posledních X dní
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
            # Vrátíme výchozí hodnoty pokud nemáme data
            return {
                'extremely_low': 0.5,  # Výchozí hodnoty, pokud nemáme historická data
                'low': 1.0,
                'average': 2.0,
                'high': 3.0
            }
        
        # Výpočet percentilů
        num_prices = len(prices)
        extremely_low_threshold = prices[int(num_prices * 0.1)]  # 10. percentil
        low_threshold = prices[int(num_prices * 0.25)]           # 25. percentil
        average_high_threshold = prices[int(num_prices * 0.75)]  # 75. percentil
        
        # Statistiky pro logování
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
        logger.info(f"Statistiky cen: min={min_price:.3f}, max={max_price:.3f}, avg={avg_price:.3f} Kč/kWh")
        
        return categories
        
    except Exception as e:
        logger.error(f"Chyba při získávání historických kategorií cen: {str(e)}")
        # Vrátíme výchozí hodnoty v případě chyby
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
        price: Cena k kategoryzaci (Kč/kWh)
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
    
def optimize_charging_plan(house_id, house_data, solar_data, consumption_data, price_data):
    """
    Optimalizace nabíjení podle cenově-efektivního přístupu.
    Pro EXTREME domy zahrnuje možnost vypínání spotřebičů k optimalizaci nákladů.
    """
    try:
        logger.info(f"ZAČÁTEK OPTIMALIZACE NABÍJENÍ PRO DŮM {house_id}")
        
        # Získáme základní parametry domu
        battery_capacity = house_data['battery_capacity']
        current_battery_level = house_data['current_battery_level']
        min_battery_level_pct = house_data['min_battery_level']
        min_battery_level = battery_capacity * (min_battery_level_pct / 100)  # Převod % na kWh
        max_charging_power = house_data['max_charging_power']
        charging_efficiency = house_data['charging_efficiency'] / 100
        risk_level = house_data['risk_level']
        
        # Získání historických kategorií cen
        price_categories = get_historical_price_categories()
        
        # Definice cílových úrovní baterie podle rizikového profilu a kategorie ceny
        target_levels = {
            'LOW': {
                'extremely_low': 0.80,  # 80% kapacity baterie
                'low': 0.60,            # 60% kapacity
                'average': 0.40,        # 40% kapacity
                'high': 0.20            # 20% kapacity
            },
            'MEDIUM': {
                'extremely_low': 0.70,  # 70% kapacity baterie
                'low': 0.50,            # 50% kapacity
                'average': 0.30,        # 30% kapacity
                'high': 0.15            # 15% kapacity
            },
            'HIGH': {
                'extremely_low': 0.50,  # 50% kapacity baterie
                'low': 0.35,            # 35% kapacity
                'average': 0.25,        # 25% kapacity
                'high': 0.10            # 10% kapacity
            },
            'EXTREME': {
                'extremely_low': 0.50,  # 50% kapacity baterie
                'low': 0.35,            # 35% kapacity
                'average': 0.25,        # 25% kapacity
                'high': 0.10            # 10% kapacity
            }
        }
        
        # Použití výchozího středního rizika, pokud nemáme definované pro daný risk_level
        target_profile = target_levels.get(risk_level, target_levels['MEDIUM'])
        
        # Počet hodin v plánovacím horizontu
        n_hours = len(price_data)
        
        # Ujistíme se, že máme konzistentní délku všech dat
        if len(solar_data) < n_hours:
            logger.warning(f"Solární data mají méně záznamů ({len(solar_data)}) než horizont plánování ({n_hours})")
            # Doplníme solární data nulami
            for i in range(len(solar_data), n_hours):
                solar_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'solar_kwh': 0,
                    'index': i
                })
                
        if len(consumption_data) < n_hours:
            logger.warning(f"Data spotřeby mají méně záznamů ({len(consumption_data)}) než horizont plánování ({n_hours})")
            # Doplníme data spotřeby průměrnými hodnotami
            avg_consumption = sum(item['consumption_kwh'] for item in consumption_data) / len(consumption_data) if consumption_data else 0.2
            for i in range(len(consumption_data), n_hours):
                consumption_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'consumption_kwh': avg_consumption,
                    'index': i
                })
        
        # Kategorizace cen pro každou hodinu a výpočet cílů s rezervou
        for hour in price_data:
            price_category = categorize_price(hour['price'], price_categories)
            hour['price_category'] = price_category
            
            # Nastavení základní cílové úrovně baterie podle kategorie a rizikového profilu
            base_target_percentage = target_profile[price_category]
            hour['base_target_level'] = battery_capacity * base_target_percentage
            hour['base_target_percentage'] = base_target_percentage * 100  # Pro logování
            
            # Přidáme 10% rezervu k cílové hodnotě (10% z hodnoty, ne absolutních)
            # Například místo 60% nabijeme na 66% (60% + 10% z 60% = 66%)
            target_with_reserve_percentage = base_target_percentage * 1.1
            
            # Uložíme cíl s rezervou
            hour['target_level'] = battery_capacity * target_with_reserve_percentage
            hour['target_percentage'] = target_with_reserve_percentage * 100  # Pro logování
        
        # Výpis kategorií cen pro tento plán
        logger.info(f"Rizikový profil: {risk_level}")
        for category, percentage in target_profile.items():
            base_target = percentage * 100
            target_with_reserve = percentage * 110
            logger.info(f"  - Kategorie '{category}': základní cíl {base_target:.1f}%, cíl s rezervou {target_with_reserve:.1f}% ({target_with_reserve*battery_capacity/100:.2f} kWh)")
        
        # Seřadíme hodiny podle ceny (od nejlevnější po nejdražší) - pro běžnou optimalizaci
        sorted_price_indices = sorted(range(n_hours), key=lambda i: price_data[i]['price'])
        
        # Funkce pro simulaci stavu baterie na základě plánu nabíjení
        def simulate_battery_levels(charging_plan, overcharge_start_idx=None):
            levels = []
            current_level = current_battery_level
            
            for i in range(n_hours):
                # Solární výroba v této hodině
                solar = solar_data[i]['solar_kwh'] if i < len(solar_data) else 0
                
                # Spotřeba v této hodině
                consumption = consumption_data[i]['consumption_kwh'] if i < len(consumption_data) else 0
                
                # Nabíjení z plánu (ze sítě)
                charging_grid = charging_plan[i] if i < len(charging_plan) else 0
                
                # Aplikujeme účinnost na veškeré nabíjení (jak ze sítě, tak ze solárů)
                effective_solar = solar * charging_efficiency
                effective_grid_charging = charging_grid * charging_efficiency
                
                # Čistý tok energie
                net_flow = effective_solar - consumption + effective_grid_charging
                
                # Nový stav baterie
                if overcharge_start_idx is not None and i >= overcharge_start_idx:
                    # Umožníme přesah kapacity pouze od zadaného indexu dále
                    current_level = max(0, current_level + net_flow)
                else:
                    # Pro ostatní hodiny omezujeme na kapacitu
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
        
        # Inicializace plánu nabíjení - žádné nabíjení
        charging_plan = [0] * n_hours
        
        # Počáteční simulace pro zjištění stavu bez nabíjení
        initial_levels = simulate_battery_levels(charging_plan)
        
        # Výpis počátečního stavu
        logger.info("Počáteční stav baterie bez nabíjení:")
        for level in initial_levels:
            logger.info(f"Hodina {level['hour']}:00 - {level['level']:.2f} kWh ({level['level']/battery_capacity*100:.1f}%)")
        
        # Definujeme minimální požadovanou úroveň baterie (high target level)
        high_category = "high"
        high_target_level = battery_capacity * target_profile[high_category]
        high_target_with_reserve = high_target_level * 1.1  # 10% rezerva
        
        logger.info(f"=== ŘEŠENÍ KRITICKÝCH HODIN ===")
        logger.info(f"Minimální požadovaná hladina baterie (high target): {high_target_level:.2f} kWh ({target_profile[high_category]*100:.1f}%)")
        logger.info(f"Minimální hladina s 10% rezervou: {high_target_with_reserve:.2f} kWh ({target_profile[high_category]*110:.1f}%)")
        
        # V části kde řešíme kritické hodiny
        for hour_idx in range(n_hours):
            # Simulujeme stav baterie s aktuálním plánem nabíjení
            current_levels = simulate_battery_levels(charging_plan)
            current_level = current_levels[hour_idx]['level']
            
            # Kontrola, zda v této hodině neklesne baterie pod minimální úroveň
            if current_level < high_target_level:
                # Máme kritickou hodinu - potřebujeme dobít před touto hodinou
                target_hour = current_levels[hour_idx]
                
                # Zjistíme kategorii ceny pro hodinu, kterou teď řešíme
                hour_price_category = price_data[hour_idx]['price_category']
                
                # Dynamicky určíme rezervu podle kategorie ceny
                if hour_price_category in ['extremely_low', 'low']:
                    # 25% rezerva pro levné hodiny
                    target_reserve_factor = 1.25
                    logger.info(f"Pro kritickou hodinu {target_hour['date']} {target_hour['hour']}:00 použita zvýšená rezerva 25% (levná kategorie: {hour_price_category})")
                else:
                    # Standardní 10% rezerva
                    target_reserve_factor = 1.10
                    logger.info(f"Pro kritickou hodinu {target_hour['date']} {target_hour['hour']}:00 použita standardní rezerva 10% (kategorie: {hour_price_category})")
                
                # Vypočteme energetický deficit s dynamickou rezervou
                energy_deficit = (high_target_level * target_reserve_factor) - current_level
                
                logger.info(f"KRITICKÁ HODINA NALEZENA: {target_hour['date']} {target_hour['hour']}:00")
                logger.info(f"Stav baterie: {current_level:.2f} kWh, Minimální požadavek: {high_target_level:.2f} kWh")
                logger.info(f"Energetický deficit: {energy_deficit:.2f} kWh (s účinností {charging_efficiency:.2f}: {energy_deficit/charging_efficiency:.2f} kWh)")
                
                # Vybere všechny předchozí hodiny (včetně aktuální)
                previous_hours_indices = list(range(hour_idx + 1))
                
                # Seřadí je podle ceny (od nejlevnější)
                previous_hours_sorted = sorted(previous_hours_indices, key=lambda idx: price_data[idx]['price'])
                
                logger.info(f"Řeším deficit pomocí {len(previous_hours_sorted)} předchozích hodin")
                
                # Deficit, který potřebujeme vyřešit (s účinností)
                remaining_deficit = energy_deficit / charging_efficiency
                
                # Procházíme předchozí hodiny od nejlevnější
                for prev_idx in previous_hours_sorted:
                    # Pokud jsme již vyřešili celý deficit, končíme
                    if remaining_deficit <= 0.01:  # Malá tolerance pro zaokrouhlovací chyby
                        break
                    
                    prev_hour = price_data[prev_idx]
                    
                    # Najdeme odpovídající solární data pro tuto hodinu
                    solar_hour = next((s for s in solar_data if s['hour'] == prev_hour['hour'] and s['date'] == prev_hour['date']), None)
                    solar_production = solar_hour['solar_kwh'] if solar_hour else 0
                    
                    # Vypočítáme maximální možné nabíjení v této hodině
                    available_charging_power = max(0, max_charging_power - solar_production)
                    
                    # Kolik již je naplánováno v této hodině
                    current_charging = charging_plan[prev_idx]
                    
                    # Kolik můžeme ještě přidat
                    additional_charging_possible = max(0, available_charging_power - current_charging)
                    
                    if additional_charging_possible <= 0:
                        logger.info(f"Nelze přidat nabíjení do hodiny {prev_hour['date']} {prev_hour['hour']}:00 - již je využita na maximum")
                        continue
                    
                    # Kolik energie potřebujeme přidat do této hodiny
                    energy_to_add = min(remaining_deficit, additional_charging_possible)
                    
                    #Zkusíme přidat nabíjení a simulovat výsledek
                    test_plan = charging_plan.copy()
                    test_plan[prev_idx] += energy_to_add
                    
                    # Simulujeme stav baterie s tímto testovacím plánem
                    test_levels = simulate_battery_levels(test_plan)
                    
                    # Kontrolujeme nový stav baterie v kritické hodině
                    new_level = test_levels[hour_idx]['level']
                    
                    # Zjistíme, kolik energie z přidaného nabíjení skutečně pomohlo
                    effective_energy_added = max(0, new_level - current_level)
                    effective_deficit_reduction = min(energy_deficit, effective_energy_added)
                    
                    # Jak velkou část z přidaného nabíjení máme skutečně použít
                    if energy_to_add > 0:
                        energy_utilization_ratio = effective_deficit_reduction / (energy_to_add * charging_efficiency)
                    else:
                        energy_utilization_ratio = 0
                    
                    # Pokud přidání nabíjení pomohlo (alespoň částečně)
                    if effective_deficit_reduction > 0:
                        # Zjistíme, kolik skutečně potřebujeme přidat (jen to, co využijeme)
                        actual_energy_to_add = energy_to_add
                        
                        # Pokud není plně využito (např. kvůli dosažení kapacity baterie)
                        if energy_utilization_ratio < 0.99:  # Tolerance pro numerické chyby
                            # Upravíme množství energie na efektivně využité
                            actual_energy_to_add = (effective_deficit_reduction / charging_efficiency)
                            logger.info(f"Upravuji množství přidané energie z {energy_to_add:.2f} kWh na {actual_energy_to_add:.2f} kWh (využití: {energy_utilization_ratio:.2f})")
                        
                        # Aktualizujeme plán nabíjení
                        charging_plan[prev_idx] += actual_energy_to_add
                        
                        # Aktualizujeme zbývající deficit
                        remaining_deficit -= actual_energy_to_add
                        
                        logger.info(f"Přidáno {actual_energy_to_add:.2f} kWh nabíjení do hodiny {prev_hour['date']} {prev_hour['hour']}:00 (cena: {prev_hour['price']:.4f} Kč/kWh)")
                        logger.info(f"Stav baterie v kritické hodině se zvýšil z {current_level:.2f} kWh na {new_level:.2f} kWh")
                        logger.info(f"Zbývající deficit: {remaining_deficit:.2f} kWh")
                    else:
                        logger.info(f"Přidání nabíjení do hodiny {prev_hour['date']} {prev_hour['hour']}:00 nepomohlo - ignoruji")
                
                # Po zpracování všech předchozích hodin aktualizujeme simulaci
                current_levels = simulate_battery_levels(charging_plan)
                current_level = current_levels[hour_idx]['level']
                
                if current_level >= high_target_with_reserve:
                    logger.info(f"KRITICKÁ HODINA VYŘEŠENA: Nový stav baterie {current_level:.2f} kWh >= {high_target_level:.2f} kWh")
                else:
                    remaining_deficit = (high_target_with_reserve - current_level) / charging_efficiency
                    logger.warning(f"NEPODAŘILO SE ZCELA VYŘEŠIT KRITICKOU HODINU: Stav baterie {current_level:.2f} kWh < {high_target_level:.2f} kWh")
                    logger.warning(f"Zbývající deficit: {remaining_deficit:.2f} kWh - nelze vyřešit pomocí dostupných hodin")
        
        logger.info(f"=== DOKONČENO ŘEŠENÍ KRITICKÝCH HODIN ===")
        
        # Standardní optimalizace pro koncový cíl
        logger.info(f"=== STANDARDNÍ OPTIMALIZACE PRO KONCOVÝ CÍL ===")
        
        # Pro každou hodinu v pořadí od nejlevnější
        for hour_idx in sorted_price_indices:
            current_hour = price_data[hour_idx]
            # Kontrolujeme vůči základnímu cíli (bez rezervy), ale plánujeme nabíjet na cíl s rezervou
            base_target = current_hour['base_target_level']
            hour_target = current_hour['target_level']  # Cíl s 10% rezervou
            
            logger.info(f"Zpracovávám hodinu {current_hour['hour']}:00 s cenou {current_hour['price']:.2f} Kč/kWh (kategorie: {current_hour['price_category']}, základní cíl: {current_hour['base_target_percentage']:.1f}%, cíl s rezervou: {current_hour['target_percentage']:.1f}%)")
            
            # Pokud jsme v drahé kategorii a je to EXTREME dům, zkusíme nejdřív vypnout spotřebiče
            if current_hour['price_category'] == 'high' and house_data['risk_level'] == 'EXTREME':
                logger.info(f"Hodina {current_hour['hour']}:00 má vysokou cenu a je EXTREME dům, zkouším optimalizaci vypnutím spotřebičů")
                
                # 1. Zjistíme kolik energie potřebujeme pro dosažení cíle
                current_levels = simulate_battery_levels(charging_plan)
                end_level = current_levels[-1]['level']
                energy_needed = max(0, base_target - end_level) / (house_data['charging_efficiency'] / 100)
                
                if energy_needed > 0:
                    logger.info(f"Potřebujeme dobít {energy_needed:.2f} kWh pro dosažení cíle")
                    
                    # 2. Zkusíme postupně vypínat spotřebiče podle priority
                    energy_saved_total = 0
                    consumption_data_modified = False
                    
                    for priority_level in [4, 3, 2]:  # Od nejnižší po nejvyšší prioritu
                        if energy_saved_total >= energy_needed:
                            break  # Pokud jsme už ušetřili dost, končíme
                            
                        logger.info(f"Zkouším vypnout spotřebiče s prioritou {priority_level}")
                        
                        # 3. Postupně rozšiřujeme okno (1-4 hodiny dozadu)
                        for window_size in range(1, 5):
                            if energy_saved_total >= energy_needed:
                                break  # Pokud jsme už ušetřili dost, končíme
                                
                            # Vypočítáme začátek okna (max 4 hodiny dozadu)
                            start_idx = max(0, hour_idx - window_size + 1)
                            
                            logger.info(f"Rozšiřuji okno na {window_size} hodin (od indexu {start_idx} do {hour_idx})")
                            
                            # 4. Získáme potenciální úspory pro toto okno a prioritu
                            potential_savings = get_potential_savings(
                                house_id, 
                                priority_level, 
                                current_hour=price_data[start_idx]['hour'],
                                have_tomorrow_prices=(len(price_data) > 24)
                            )
                            
                            # Filtrujeme jen úspory v našem okně
                            window_savings = [s for s in potential_savings if start_idx <= s['index'] <= hour_idx]
                            total_window_savings = sum(s['savings_kwh'] for s in window_savings)
                            
                            if total_window_savings > 0:
                                logger.info(f"Nalezeno {total_window_savings:.2f} kWh úspor vypnutím spotřebičů priority {priority_level} v okně {window_size} hodin")
                                
                                # 5. Aplikujeme úspory - vytvoříme neaktivní okno pro spotřebiče
                                start_date = price_data[start_idx]['date']
                                end_date = price_data[hour_idx]['date']
                                start_hour = price_data[start_idx]['hour']
                                end_hour = price_data[hour_idx]['hour'] + 1  # +1 protože end_hour je exkluzivní
                                
                                inactive_window = {
                                    'start_date': start_date.strftime('%Y-%m-%d'),
                                    'end_date': end_date.strftime('%Y-%m-%d'),
                                    'start_hour': start_hour,
                                    'end_hour': end_hour
                                }
                                
                                apply_inactive_window(house_id, priority_level, inactive_window)
                                
                                # 6. Aktualizujeme předpověď spotřeby
                                for sav in window_savings:
                                    for i, cons in enumerate(consumption_data):
                                        if cons['index'] == sav['index']:
                                            consumption_data[i]['consumption_kwh'] -= sav['savings_kwh']
                                            consumption_data_modified = True
                                
                                energy_saved_total += total_window_savings
                                
                                logger.info(f"Aktualizována předpověď spotřeby, ušetřeno celkem {energy_saved_total:.2f} kWh")
                    
                    # 7. Po úpravě spotřeby znovu simulujeme stav baterie
                    if consumption_data_modified:
                        current_levels = simulate_battery_levels(charging_plan)
                        end_level = current_levels[-1]['level']
                        logger.info(f"Po vypnutí spotřebičů bude končený stav baterie {end_level:.2f} kWh")
                        
                        # Zkontrolujeme, zda stále potřebujeme nabíjet v této hodině
                        if end_level >= base_target:
                            logger.info(f"Vypnutí spotřebičů vyřešilo problém, není potřeba nabíjet v drahé hodině {current_hour['hour']}:00")
                            continue  # Přeskočíme tuto hodinu a přejdeme k další
                        else:
                            logger.info(f"I po vypnutí spotřebičů je stále potřeba nabíjet v drahé hodině {current_hour['hour']}:00")
                            # Pokračujeme standardním algoritmem nabíjení pro tuto hodinu
            
            # 1. Zjistíme, jaký bude stav baterie na konci období s aktuálním plánem
            current_levels = simulate_battery_levels(charging_plan)
            end_level = current_levels[-1]['level']
            
            # 2. Plánování nabíjení pro aktuální hodinu
            # Kontrolujeme vůči základnímu cíli (bez rezervy)
            if end_level < base_target:
                # Získáme informace o solární výrobě v této hodině
                solar_hour = next((s for s in solar_data if s['hour'] == current_hour['hour'] and s['date'] == current_hour['date']), None)
                solar_production = solar_hour['solar_kwh'] if solar_hour else 0
                
                # Maximální nabíjecí výkon baterie je omezení pro celkový přísun energie (síť + solar)
                # Musíme odečíst solární výrobu, abychom dostali kolik můžeme ještě nabíjet ze sítě
                available_charging_power = max(0, max_charging_power - solar_production)
                
                # Kolik je již naplánováno (mohlo být přidáno při řešení kritických hodin)
                current_planned_charging = charging_plan[hour_idx]
                
                # Kolik můžeme ještě přidat
                additional_charging_possible = max(0, available_charging_power - current_planned_charging)
                
                if additional_charging_possible <= 0:
                    logger.info(f"Hodina {current_hour['hour']}:00 již má naplánované maximum nabíjení {current_planned_charging:.2f} kWh, není možné přidat další.")
                    continue
                
                logger.info(f"Plánuji nabíjení pro hodinu {current_hour['hour']}:00")
                
                # Simulujeme plán s maximálním nabíjením v této hodině
                test_charging_plan = charging_plan.copy()
                test_charging_plan[hour_idx] = available_charging_power  # Zkusíme plné nabíjení
                test_levels = simulate_battery_levels(test_charging_plan, hour_idx)
                
                # Kontrolujeme:
                # 1. Přesah 100% kapacity (v jakékoliv budoucí hodině)
                # 2. Přesah cíle S REZERVOU na konci plánovacího období
                
                # Hledáme nejvyšší přesah kapacity baterie
                max_level = 0
                max_level_hour = None
                capacity_excess = 0
                
                for i, level in enumerate(test_levels[hour_idx:], hour_idx):
                    if level['level'] > max_level:
                        max_level = level['level']
                        max_level_hour = level['hour']
                        
                if max_level > battery_capacity * 0.999:
                    capacity_excess = max_level - battery_capacity
                    logger.info(f"V hodině {max_level_hour}:00 by baterie překročila kapacitu o {capacity_excess:.2f} kWh")
                
                # Zjišťujeme přesah cíle S REZERVOU na konci období
                end_test_level = test_levels[-1]['level']
                target_excess = 0
                
                if end_test_level > hour_target:
                    target_excess = end_test_level - hour_target
                    logger.info(f"Konečný stav baterie by překročil cíl s rezervou {hour_target:.2f} kWh o {target_excess:.2f} kWh")
                
                # Vypočítáme, kolik energie musíme odebrat (větší z obou přesahů)
                energy_excess = max(capacity_excess, target_excess)
                
                # Určíme finální dodatečné nabíjení 
                additional_charging = additional_charging_possible
                
                if energy_excess > 0:
                    # Musíme snížit nabíjení o přesah
                    excess_charging = energy_excess / charging_efficiency
                    additional_charging = max(0, additional_charging_possible - excess_charging)
                    logger.info(f"Snižuji dodatečné nabíjení o {excess_charging:.2f} kWh na {additional_charging:.2f} kWh")
                
                # Aktualizujeme plán nabíjení
                charging_plan[hour_idx] = current_planned_charging + additional_charging
                
                # Aktualizujeme simulaci a zkontrolujeme výsledek
                current_levels = simulate_battery_levels(charging_plan)
                end_level = current_levels[-1]['level']
                
                # Kontrolujeme vůči základnímu cíli (bez rezervy)
                target_reached = end_level >= base_target
                reserve_target_reached = end_level >= hour_target
                
                logger.info(f"Finální plán pro hodinu {current_hour['hour']}:00:")
                logger.info(f" - Původní naplánované nabíjení: {current_planned_charging:.2f} kWh")
                logger.info(f" - Přidané nabíjení: {additional_charging:.2f} kWh")
                logger.info(f" - Celkové nabíjení ze sítě: {charging_plan[hour_idx]:.2f} kWh")
                logger.info(f" - Solární výroba v této hodině: {solar_production:.2f} kWh")
                logger.info(f" - Celkový přísun energie: {(charging_plan[hour_idx] + solar_production):.2f} kWh")
                logger.info(f" - Max. nabíjecí výkon baterie: {max_charging_power:.2f} kW")
                logger.info(f" - Dostupný výkon pro nabíjení ze sítě: {available_charging_power:.2f} kW")
                logger.info(f" - Konečný stav baterie: {end_level:.2f} kWh ({end_level/battery_capacity*100:.1f}%)")
                logger.info(f" - Základní cíl splněn: {'ANO' if target_reached else 'NE'}")
                logger.info(f" - Cíl s rezervou splněn: {'ANO' if reserve_target_reached else 'NE'}")
            
            else:
                logger.info(f"Konečný stav baterie {end_level:.2f} kWh již splňuje základní cíl {base_target:.2f} kWh, není potřeba nabíjet")
        
        # Finální stav baterie po všech úpravách
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
                
                logger.warning(f"PŘETRVÁVAJÍCÍ KRITICKÁ HODINA: {level['date']} {level['hour']}:00 - Stav baterie: {level['level']:.2f} kWh, " +
                                f"Minimální požadavek: {high_target_level:.2f} kWh, Deficit: {energy_deficit:.2f} kWh")
        
        if not critical_hours_after:
            logger.info("Po optimalizaci nebyly nalezeny žádné kritické hodiny.")
        else:
            logger.info(f"Po optimalizaci přetrvává {len(critical_hours_after)} kritických hodin, kde baterie klesá pod minimální požadovanou úroveň.")
        
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
        
        # Logování výsledků
        logger.info("Finální plán nabíjení:")
        for plan in final_plan:
            if plan['planned_charging_kwh'] > 0:
                logger.info(f"Hodina {plan['hour']}:00 - nabíjení {plan['planned_charging_kwh']:.2f} kWh (cena: {plan['price']:.2f} Kč/kWh, kategorie: {plan['price_category']})")
        
        # Výpočet celkových nákladů
        total_energy = sum(plan['planned_charging_kwh'] for plan in final_plan)
        total_cost = sum(plan['planned_charging_kwh'] * plan['price'] for plan in final_plan)
        
        logger.info(f"Celkové nabíjení: {total_energy:.2f} kWh")
        logger.info(f"Celkové náklady: {total_cost:.2f} Kč")
        
        # Výpis stavu baterie na konci plánovacího horizontu
        if final_plan:
            last_plan = final_plan[-1]
            logger.info(f"Konečný stav baterie: {last_plan['battery_level']:.2f} kWh ({last_plan['battery_percent']:.1f}%)")
        
        # Výpis finálního plánu v přehledné tabulce
        logger.info("=" * 150)
        logger.info(f"PLÁN NABÍJENÍ PRO DŮM {house_id}")
        logger.info("=" * 150)
        logger.info(f"| {'Datum':<10} | {'Hodina':<8} | {'Cena':>10} | {'Spotřeba':>10} | {'Solár':>7} | {'Nabíjení':>10} | {'Stav baterie':>15} | {'Stav baterie':>15} | {'Kategorie':<15} | {'Zákl. cíl':>10} | {'Cíl s rez.':>10} |")
        logger.info(f"| {'':<10} | {'':<8} | {'(Kč/kWh)':>10} | {'(kWh)':>10} | {'(kWh)':>7} | {'(kWh)':>10} | {'(kWh)':>15} | {'(%)':>15} | {'ceny':<15} | {'(%)':>10} | {'(%)':>10} |")
        logger.info(f"|:{'-'*10}|:{'-'*8}|{'-'*10}:|{'-'*10}:|{'-'*7}:|{'-'*10}:|{'-'*15}:|{'-'*15}:|:{'-'*15}|{'-'*10}:|{'-'*10}:|")
        
        for plan in final_plan:
            date_str = plan['date'].strftime('%Y-%m-%d')
            hour_str = f"{plan['hour']}:00"
            price_str = f"{plan['price']:.3f}"
            consumption_str = f"{plan['consumption']:.3f}"
            solar_str = f"{plan['solar_production']:.3f}"
            charging_str = f"{plan['planned_charging_kwh']:.3f}"
            level_str = f"{plan['battery_level']:.3f}"
            percent_str = f"{plan['battery_percent']:.1f}"
            base_target_str = f"{plan['base_target_percent']:.1f}"
            target_str = f"{plan['target_percent']:.1f}"
            
            # Pro lepší čitelnost kategorie cen
            category_map = {
                'extremely_low': 'Extrémně nízká',
                'low': 'Nízká',
                'average': 'Průměrná',
                'high': 'Vysoká'
            }
            category_str = category_map.get(plan['price_category'], plan['price_category'])
            
            logger.info(f"| {date_str:<10} | {hour_str:<8} | {price_str:>10} | {consumption_str:>10} | {solar_str:>7} | {charging_str:>10} | {level_str:>15} | {percent_str:>15} | {category_str:<15} | {base_target_str:>10} | {target_str:>10} |")
        
        logger.info("=" * 150)
        
        return final_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI OPTIMALIZACI NABÍJENÍ: {str(e)}", exc_info=True)
        # V případě chyby vracíme prázdný plán
        return []
    
def save_charging_schedule(house_id, charging_plan):
    """
    Uloží plán nabíjení do databáze.
    Nahrazuje stávající plány pro daný dům.
    Ignoruje velmi malé hodnoty nabíjení (menší než 0.01 kWh).
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        # Nejprve smažeme existující plány
        cur.execute("""
            DELETE FROM api_chargingschedule
            WHERE house_id = %s
        """, [house_id])
        
        # Uložíme nové plány, ignorujeme zanedbatelně malé hodnoty
        saved_count = 0
        MIN_CHARGING_THRESHOLD = 0.01  # Minimální hodnota v kWh, která se bude ukládat
        
        for plan_item in charging_plan:
            hour = plan_item['hour']
            amount = plan_item['planned_charging_kwh']
            date = plan_item['date']
            
            # Přeskočíme velmi malé hodnoty nabíjení
            if amount < MIN_CHARGING_THRESHOLD:
                logger.debug(f"Ignoruji zanedbatelné nabíjení {amount:.10f} kWh pro hodinu {hour}:00")
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
    """
    Kompletní proces plánování nabíjení pro jeden dům.
    Zohledňuje dostupnost dat o cenách elektřiny (k dispozici v 17:00 na další den).
    """
    try:
        logger.info(f"ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        
        # 1. Zjistíme aktuální čas a posuneme plánování od následující hodiny
        current_time = datetime.now()
        # Posun na další hodinu - skripty se spouští v xx:59, takže plánujeme od další hodiny
        next_hour = current_time.hour + 1
        current_date = current_time.date()
        tomorrow = current_date + timedelta(days=1)
        
        # Určíme, zda máme k dispozici data o cenách elektřiny na zítřek
        # Pokud je aktuální hodina >= 17, máme data na zítřek
        have_tomorrow_prices = next_hour >= 17
        
        if have_tomorrow_prices:
            logger.info(f"Aktuální čas: {current_time.strftime('%H:%M')} - Máme k dispozici ceny na zítřek")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {tomorrow.strftime('%Y-%m-%d')} 23:59"
        else:
            logger.info(f"Aktuální čas: {current_time.strftime('%H:%M')} - Ceny na zítřek ještě nejsou k dispozici")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {current_date.strftime('%Y-%m-%d')} 23:59"
        
        logger.info(f"Plánovací horizont: {planning_horizon}")
        
        # 2. Získání dat o domu
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} nenalezen")
            return False
        
        # 3. Získání cen elektřiny
        price_data = get_price_data(
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        if not price_data:
            logger.error("PLÁNOVÁNÍ NABÍJENÍ: Žádná data o cenách elektřiny nebyla nalezena")
            return False
            
        # 4. Získání predikce solární výroby
        solar_data = get_solar_prediction(
            house_power=house_data['solar_power'],
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        # 5. Získání predikce spotřeby
        consumption_data = get_consumption_prediction(
            house_id, 
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        # 6. Optimalizace plánu nabíjení s novým algoritmem využívajícím historické kategorie cen
        charging_plan = optimize_charging_plan(
            house_id,
            house_data,
            solar_data,
            consumption_data,
            price_data
        )
        
        # 7. Uložení plánu do databáze
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
        
        # Získání seznamu aktivních domů
        active_houses = get_active_houses()
        logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Zpracovávám {len(active_houses)} aktivních domů")
        
        # Plánování pro každý dům
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