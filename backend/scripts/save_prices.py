import psycopg2
from datetime import date, timedelta
import json
import requests

def fetch_price_data():
    url = "https://spotovaelektrina.cz/api/v1/price/get-prices-json"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")

def save_tomorrow_prices():
    # Získání dat z API
    data = fetch_price_data()
    
    # Připojení k databázi
    conn = psycopg2.connect(
        dbname="fve_db",
        user="postgres",
        password="heslo",
        host="db"
    )
    cur = conn.cursor()
    
    tomorrow = date.today() + timedelta(days=1)
    
    try:
        for hour_data in data['hoursTomorrow']:
            cur.execute("""
                INSERT INTO api_pricedata (date, hour, price_czk, level, level_num)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date, hour) 
                DO UPDATE SET 
                    price_czk = EXCLUDED.price_czk,
                    level = EXCLUDED.level,
                    level_num = EXCLUDED.level_num
            """, (
                tomorrow,
                hour_data['hour'],
                hour_data['priceCZK'],
                hour_data['level'],
                hour_data['levelNum']
            ))
        
        conn.commit()
        print("Data byla úspěšně uložena")
    except Exception as e:
        print(f"Chyba: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    save_tomorrow_prices()