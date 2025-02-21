import psycopg2
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message}s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def get_active_houses():
    """
    Získá ID všech aktivních domů z databáze.
    
    Returns:
        list: Seznam ID aktivních domů
    """
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
    """
    Získá spotové ceny od aktuální hodiny do konce zítřejšího dne.
    
    Returns:
        dict: Slovník s cenami {datum: {hodina: cena_czk}}
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
        current_hour = current_time.hour

        cur.execute("""
            SELECT date, hour, price_czk 
            FROM api_pricedata 
            WHERE (date = %s AND hour >= %s) OR date = %s
            ORDER BY date, hour
        """, [today, current_hour, tomorrow])
        
        prices = {}
        rows = cur.fetchall()
        
        for date, hour, price in rows:
            date_str = date.strftime('%Y-%m-%d')
            if date_str not in prices:
                prices[date_str] = {}
            prices[date_str][hour] = price / 1000  # Převod z Kč/MWh na Kč/kWh
        
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
    """
    Získá potřebná data pro plánování nabíjení pro jeden dům.
    
    Args:
        house_id: ID domu
        
    Returns:
        dict: Slovník s parametry domu
    """
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

def get_solar_prediction(house_power, solar_variation=1.0):
    """
    Získá predikci solární výroby na zbytek dne a další den.
    Přepočítá predikci podle instalovaného výkonu domu.
    
    Args:
        house_power (float): Instalovaný výkon solárů domu v kWp
        solar_variation (float): Variace výkonu (defaultně 1.0)
        
    Returns:
        dict: Předpověď výroby {datum: {hodina: výroba_wh}}
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
        current_hour = current_time.hour

        # Získání predikcí pro zbytek dneška a celý zítřek
        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE (DATE(timestamp) = %s AND EXTRACT(HOUR FROM timestamp) >= %s) 
               OR DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today, current_hour, tomorrow])
        
        production = {}
        rows = cur.fetchall()
        
        # Přepočet podle výkonu domu (predikce jsou pro 20kWp)
        power_ratio = house_power / 20
        
        for timestamp, wh in rows:
            date_str = timestamp.strftime('%Y-%m-%d')
            minutes = timestamp.minute
            
            if date_str not in production:
                production[date_str] = {}
            
            # Pokud čas končí :00, použijeme aktuální hodinu
            # Jinak použijeme následující hodinu
            hour = timestamp.hour if minutes == 0 else timestamp.hour + 1
            
            # Přepočet a aplikace variace
            production[date_str][hour] = wh * power_ratio * solar_variation
        
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
    """
    Získá predikci spotřeby na základě historických dat.
    Rozdělí dny na víkendy a všední dny, spočítá průměrnou spotřebu pro každou hodinu.
    
    Args:
        house_id: ID domu
        
    Returns:
        dict: Předpověď spotřeby {
            'weekday': {hodina: spotřeba_wh},
            'weekend': {hodina: spotřeba_wh}
        }
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        # Data za posledních 30 dní
        today = datetime.now().date()
        start_date = today - timedelta(days=30)
        
        # SQL dotaz pro získání součtů po hodinách, rozděleno na víkendy a všední dny
        cur.execute("""
            WITH hourly_consumption AS (
                SELECT 
                    date,
                    EXTRACT(HOUR FROM time::time) as hour,
                    EXTRACT(DOW FROM date) as day_of_week,
                    SUM(
                        (jsonb_array_elements(appliance_consumption)->>'consumption_w')::float
                    ) as total_wh
                FROM api_consumptiondata
                WHERE house_id = %s 
                    AND date >= %s
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
        
        # Zpracování výsledků
        consumption = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            consumption[day_type][int(hour)] = avg_consumption
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return consumption
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def predict_battery_state(house_id):
    """
    Předpoví stav baterie pro následující hodiny.
    Zatím pouze se solární predikcí, bez započítání spotřeby.
    
    Args:
        house_id: ID domu
    """
    try:
        # Získání dat o domu
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PREDIKCE STAVU BATERIE: Dům {house_id} nenalezen")
            return None
            
        # Získání solární predikce
        solar_prediction = get_solar_prediction(
            house_data['solar_power']
        )
        
        # Získání predikce spotřeby
        consumption_prediction = get_consumption_prediction(house_id)
        
        # Zde budeme dále implementovat výpočet stavu baterie
        logger.info(f"PREDIKCE STAVU BATERIE: Data načtena pro dům {house_id}")
        
        return {
            'house_data': house_data,
            'solar_prediction': solar_prediction,
            'consumption_prediction': consumption_prediction
        }
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PREDIKCI STAVU BATERIE: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        active_houses = get_active_houses()
        print("\nAktivní domy:", active_houses)
        
        for house_id in active_houses:
            print(f"\nPredikce pro dům {house_id}:")
            prediction = predict_battery_state(house_id)
            
            if prediction:
                house_data = prediction['house_data']
                solar_prediction = prediction['solar_prediction']
                consumption_prediction = prediction['consumption_prediction']
                
                print("\nData domu:")
                for key, value in house_data.items():
                    print(f"  {key}: {value}")
                
                print("\nPredikce solární výroby:")
                for date in sorted(solar_prediction.keys()):
                    print(f"\n{date}:")
                    for hour in sorted(solar_prediction[date].keys()):
                        wh = solar_prediction[date][hour]
                        print(f"  {hour:02d}:00 - {wh:.2f} Wh")
                
                print("\nPrůměrná spotřeba - všední dny:")
                for hour in range(24):
                    if hour in consumption_prediction['weekday']:
                        print(f"  {hour:02d}:00 - {consumption_prediction['weekday'][hour]:.2f} Wh")
                
                print("\nPrůměrná spotřeba - víkendy:")
                for hour in range(24):
                    if hour in consumption_prediction['weekend']:
                        print(f"  {hour:02d}:00 - {consumption_prediction['weekend'][hour]:.2f} Wh")
                        
    except Exception as e:
        print(f"Chyba: {str(e)}")