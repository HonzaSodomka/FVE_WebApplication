import psycopg2
import logging
from datetime import datetime, timedelta

# Nastavení loggeru
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
        
        # Dotaz na ID aktivních domů
        cur.execute("""
            SELECT id 
            FROM api_house 
            WHERE is_active = true
        """)
        
        # Získání výsledků
        active_houses = [row[0] for row in cur.fetchall()]
        logger.info(f"Nalezeno {len(active_houses)} aktivních domů")
        
        return active_houses
        
    except Exception as e:
        logger.error(f"Chyba při získávání aktivních domů: {str(e)}")
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
                logger.info(f"Načtena data pro dům {house_id}")
                logger.debug(f"Data domu {house_id}: {houses_data[house_id]}")
            else:
                logger.warning(f"Dům s ID {house_id} nebyl nalezen")
        
        return houses_data
        
    except Exception as e:
        logger.error(f"Chyba při získávání dat domů: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    try:
        active_houses = get_active_houses()
        print(f"Aktivní domy: {active_houses}")
        
        houses_data = get_houses_data(active_houses)
        for house_id, data in houses_data.items():
            print(f"\nData pro dům {house_id}:")
            for key, value in data.items():
                print(f"  {key}: {value}")
    except Exception as e:
        print(f"Chyba: {str(e)}")