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

if __name__ == "__main__":
    try:
        active_houses = get_active_houses()
        print(f"Aktivní domy: {active_houses}")
    except Exception as e:
        print(f"Chyba: {str(e)}")