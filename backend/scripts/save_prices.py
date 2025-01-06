import psycopg2
from datetime import date, timedelta
import json
import requests
import logging

# Nastavíme logging do stejného souboru jako Django
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',  # Stejný soubor jako používá Django
    filemode='a'  # 'a' znamená append - přidává záznamy na konec souboru
)

logger = logging.getLogger('api')

def fetch_price_data():
    url = "https://spotovaelektrina.cz/api/v1/price/get-prices-json"
    #Stáhne data z URL
    logger.info(f"Request for price data sent to{url}")
    response = requests.get(url)
    #200 = úspěšný požadavek
    if response.status_code == 200:
        logger.info("Successfully fetched price data from API")
        return response.json()
    else:
        logger.error(f"API request failed with status code: {response.status_code}")
        raise Exception(f"Failed to fetch data: {response.status_code}")

def save_tomorrow_prices():
    # Získání dat z API
    data = fetch_price_data()
    
    # Připojení k databázi
    logger.info("Connecting to database")
    conn = psycopg2.connect(
        dbname="fve_db",
        user="postgres",
        password="heslo",
        host="db"
    )
    cur = conn.cursor()
    
    #Zítřek = dnešek + 1 den
    tomorrow = date.today() + timedelta(days=1)
    logger.info(f"Saving price data for {tomorrow}")
    
    try:
        records_updated = 0
        for hour_data in data['hoursTomorrow']:
            #ON CONFLICT zajistí, že existující data se přepíší při aktualizaci
            cur.execute("""
                INSERT INTO api_pricedata (date, hour, price_czk, level, level_num)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date, hour) 
                DO UPDATE SET 
                    price_czk = EXCLUDED.price_czk,
                    level = EXCLUDED.level,
                    level_num = EXCLUDED.level_num
            """, (
                #Hodnoty dosazující se za %s
                tomorrow,
                hour_data['hour'],
                hour_data['priceCZK'],
                hour_data['level'],
                hour_data['levelNum']
            ))
            records_updated += 1
        
        #Nahrání do db
        conn.commit()
        logger.info(f"Successfully saved {records_updated} price records for {tomorrow}")
        
    except KeyError as e:
        logger.error(f"Unexpected API response format: {str(e)}")
        conn.rollback()
    except psycopg2.Error as e:
        #Zrušení změn v případě chyby
        logger.error(f"Database error: {str(e)}")
        conn.rollback()
    finally:
        #Uzavření spojení
        cur.close()
        conn.close()
        logger.debug("Database connection closed")

if __name__ == "__main__":
    save_tomorrow_prices()