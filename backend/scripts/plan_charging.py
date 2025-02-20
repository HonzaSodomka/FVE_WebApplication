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

def get_houses_data(house_ids):
    """
    Získá potřebná data pro plánování nabíjení pro zadané domy.
    
    Args:
        house_ids (list): Seznam ID domů
        
    Returns:
        dict: Slovník s daty domů {house_id: {parametry}}
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        houses_data = {}
        for house_id in house_ids:
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
                houses_data[house_id] = {
                    'risk_level': row[0],
                    'solar_power': row[1],
                    'battery_capacity': row[2],
                    'current_battery_level': row[3],
                    'min_battery_level': row[4],
                    'max_charging_power': row[5],
                    'charging_efficiency': row[6]
                }
        
        logger.info(f"NAČÍTÁNÍ DAT DOMŮ: Úspěšně načtena data pro {len(houses_data)} domů")
        return houses_data
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ DAT DOMŮ: {str(e)}")
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

        # Získání cen pro zbytek dneška a celý zítřek
        cur.execute("""
            SELECT date, hour, price_czk 
            FROM api_pricedata 
            WHERE (date = %s AND hour >= %s) OR date = %s
            ORDER BY date, hour
        """, [today, current_hour, tomorrow])
        
        prices = {}
        rows = cur.fetchall()
        
        # Organizace dat do slovníku
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

if __name__ == "__main__":
    try:
        # Test aktivních domů
        active_houses = get_active_houses()
        print("\nAktivní domy:")
        print(active_houses)
        
        # Test dat domů
        houses_data = get_houses_data(active_houses)
        print("\nData domů:")
        for house_id, data in houses_data.items():
            print(f"\nDům {house_id}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
        
        # Test cenových dat
        price_data = get_price_data()
        print("\nCenová data:")
        for date in price_data:
            print(f"\nDatum: {date}")
            for hour, price in price_data[date].items():
                print(f"  {hour}:00 - {price:.2f} Kč/kWh")
                
    except Exception as e:
        logger.error(f"CHYBA PŘI SPUŠTĚNÍ SKRIPTU: {str(e)}")
        print(f"Chyba: {str(e)}")