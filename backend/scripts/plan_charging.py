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
            WHERE is_active = true
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

def get_price_data():
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
        current_hour = current_time.hour

        cur.execute("""
            SELECT date, hour, price_czk 
            FROM api_pricedata 
            WHERE (date = %s AND hour >= %s) OR date = %s
            ORDER BY date, hour
        """, [today, current_hour, tomorrow])
        
        prices = {}
        rows = cur.fetchall()
        
        # Přidáme výpis hodin a cen
        print("Ceny elektřiny:")
        for date, hour, price in rows:
            date_str = date.strftime('%Y-%m-%d')
            if date_str not in prices:
                prices[date_str] = {}
            prices[date_str][hour] = price / 1000  # Převod z Kč/MWh na Kč/kWh
            
            print(f"{date_str} {hour:02d}:00 - {prices[date_str][hour]:.3f} Kč/kWh")
        
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

def get_solar_prediction(house_power, charging_efficiency):
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
        current_hour = current_time.hour

        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE (DATE(timestamp) = %s AND EXTRACT(HOUR FROM timestamp) >= %s) 
               OR DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today, current_hour, tomorrow])
        
        production = {}
        rows = cur.fetchall()
        
        power_ratio = house_power / 20
        efficiency_multiplier = charging_efficiency / 100
        
        print(f"\nPredikce solární výroby (pro {house_power}kWp, účinnost nabíjení {charging_efficiency}%):")
        
        # První zpracování pro nalezení prvního nenulového záznamu pro každý den
        first_nonzero = {}
        for timestamp, wh in rows:
            date_str = timestamp.strftime('%Y-%m-%d')
            hour = timestamp.hour
            
            if wh > 0:  # Pokud najdeme nenulovou hodnotu
                if date_str not in first_nonzero:  # a ještě nemáme pro tento den
                    first_nonzero[date_str] = hour  # uložíme hodinu
        
        # Druhé zpracování pro skutečné uložení dat
        for timestamp, wh in rows:
            date_str = timestamp.strftime('%Y-%m-%d')
            minutes = timestamp.minute
            hour = timestamp.hour
            
            # Přeskočíme nulové hodnoty před prvním nenulovým záznamem dne
            if hour < first_nonzero.get(date_str, 0) and wh == 0:
                continue
                
            if date_str not in production:
                production[date_str] = {}
            
            # Pokud nejsme na začátku hodiny, posuneme záznam do další hodiny
            if minutes > 0:
                hour = (hour + 1) % 24
                # Pokud přecházíme přes půlnoc, změníme datum
                if hour == 0:
                    date = timestamp.date() + timedelta(days=1)
                    date_str = date.strftime('%Y-%m-%d')
                    if date_str not in production:
                        production[date_str] = {}
            
            # Přepočet na instalovaný výkon a aplikace účinnosti nabíjení
            adjusted_wh = wh * power_ratio * efficiency_multiplier
            production[date_str][hour] = adjusted_wh
            
            # Výpis hodnot
            print(f"{date_str} {hour:02d}:00 - {adjusted_wh:.1f} Wh")
        
        logger.info(f"NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Načteno {len(rows)} záznamů pro {house_power}kWp")
        
        if not rows:
            logger.warning("NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Žádné záznamy nenalezeny")
        
        return production
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_consumption_prediction(house_id):
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
        current_hour = current_time.hour
        
        # Zjistíme typ dnů (víkend/všední)
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        # Načteme historická data za posledních 30 dní
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
        """, [house_id, start_date])
        
        rows = cur.fetchall()
        
        # Průměrná spotřeba podle typů dnů
        averages = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            averages[day_type][int(hour)] = avg_consumption
        
        # Vytvoříme predikci jen pro požadované hodiny
        prediction = {
            today.strftime('%Y-%m-%d'): {},
            tomorrow.strftime('%Y-%m-%d'): {}
        }
        
        # Pro dnešek od aktuální hodiny
        today_type = 'weekend' if is_today_weekend else 'weekday'
        print(f"\nPredikce spotřeby pro {today.strftime('%Y-%m-%d')} ({today_type}):")
        for hour in range(current_hour, 24):
            consumption = averages[today_type].get(hour, 0)
            prediction[today.strftime('%Y-%m-%d')][hour] = consumption
            print(f"{today.strftime('%Y-%m-%d')} {hour:02d}:00 - {consumption:.1f} Wh")
            
        # Pro zítřek všechny hodiny
        tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
        print(f"\nPredikce spotřeby pro {tomorrow.strftime('%Y-%m-%d')} ({tomorrow_type}):")
        for hour in range(24):
            consumption = averages[tomorrow_type].get(hour, 0)
            prediction[tomorrow.strftime('%Y-%m-%d')][hour] = consumption
            print(f"{tomorrow.strftime('%Y-%m-%d')} {hour:02d}:00 - {consumption:.1f} Wh")
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return prediction
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def calculate_battery_levels(current_level, solar_prediction, consumption_prediction, battery_capacity, is_weekend):
    battery_levels = {}
    current_time = datetime.now()
    
    for date in sorted(solar_prediction.keys()):
        battery_levels[date] = {}
        
        # Pro každou hodinu 0-23
        for hour in range(24):
            # Přeskočit už uplynulé hodiny (kromě aktuální)
            if date == current_time.date().strftime('%Y-%m-%d') and hour < current_time.hour:
                continue
                
            day_type = 'weekend' if is_weekend else 'weekday'
            consumption = consumption_prediction[day_type].get(hour, 0)
            production = solar_prediction[date].get(hour, 0)
            
            # Změna stavu baterie (ve Wh)
            delta = (production - consumption) / 1000  # převod na kWh
            new_level = current_level + delta
            new_level = max(0, min(new_level, battery_capacity))
            
            # Uložíme původní i nový stav plus změnu
            battery_levels[date][hour] = {
                'original_level': current_level,
                'new_level': new_level,
                'delta': delta
            }
            
            current_level = new_level
            
        logger.info(f"VÝPOČET STAVU BATERIE: Vypočteno {len(battery_levels[date])} hodin pro {date}")
    
    return battery_levels

def predict_battery_state(house_id):
    try:
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PREDIKCE STAVU BATERIE: Dům {house_id} nenalezen")
            return None
            
        solar_prediction = get_solar_prediction(
            house_data['solar_power']
        )
        
        consumption_prediction = get_consumption_prediction(house_id)
        
        current_time = datetime.now()
        is_weekend = current_time.weekday() >= 5
        
        battery_levels = calculate_battery_levels(
            current_level=house_data['current_battery_level'],
            solar_prediction=solar_prediction,
            consumption_prediction=consumption_prediction,
            battery_capacity=house_data['battery_capacity'],
            is_weekend=is_weekend
        )
        
        logger.info(f"PREDIKCE STAVU BATERIE: Data načtena pro dům {house_id}")
        
        return {
            'house_data': house_data,
            'solar_prediction': solar_prediction,
            'consumption_prediction': consumption_prediction,
            'battery_levels': battery_levels
        }
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PREDIKCI STAVU BATERIE: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        # 1. Získáme aktivní domy
        active_houses = get_active_houses()
        print("\nAktivní domy:", active_houses)
        
        # 2. Získáme ceny elektřiny
        prices = get_price_data()
        
        # 3. Pro každý aktivní dům
        for house_id in active_houses:
            print(f"\n{'='*50}")
            print(f"Dům ID: {house_id}")
            print(f"{'='*50}")
            
            # Načteme data o domu
            house_data = get_house_data(house_id)
            print("\nParametry domu:")
            for key, value in house_data.items():
                print(f"{key}: {value}")
                
            # Získáme predikci solární výroby
            solar_data = get_solar_prediction(house_data['solar_power'], house_data['charging_efficiency'])
            
            # Získáme predikci spotřeby
            consumption_data = get_consumption_prediction(house_id)
            
    except Exception as e:
        print(f"Chyba: {str(e)}")
        logger.error(f"CHYBA PŘI BĚHU SKRIPTU: {str(e)}")