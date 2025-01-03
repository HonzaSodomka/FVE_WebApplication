import requests
from datetime import datetime, date, timedelta
import psycopg2
import json

def fetch_solar_forecast():
    latitude = 50.7728417
    longitude = 15.0721458
    declination = 30
    azimuth = 0
    power = 20  # kWp

    url = f"https://api.forecast.solar/estimate/{latitude}/{longitude}/{declination}/{azimuth}/{power}"
    
    headers = {
        'accept': 'application/json',
        'X-Delimiter': '|',
        'X-Separator': ';'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")

def save_solar_forecast():
    conn = psycopg2.connect(
        dbname="fve_db",
        user="postgres",
        password="heslo",
        host="db"
    )
    cur = conn.cursor()
    
    try:
        data = fetch_solar_forecast()
        tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Zpracování dat z watthours_period
        for timestamp_str, wh_period in data['result']['watt_hours_period'].items():
            # Kontrola jestli je záznam pro zítřejší den
            if timestamp_str.startswith(tomorrow):
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                watts = data['result']['watts'].get(timestamp_str, 0)
                wh_cumulative = data['result']['watt_hours'].get(timestamp_str, 0)
                
                cur.execute("""
                    INSERT INTO api_solardata (timestamp, watts, watt_hours_period, watt_hours_cumulative)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (timestamp) 
                    DO UPDATE SET 
                        watts = EXCLUDED.watts,
                        watt_hours_period = EXCLUDED.watt_hours_period,
                        watt_hours_cumulative = EXCLUDED.watt_hours_cumulative
                """, (
                    timestamp,
                    watts,
                    wh_period,
                    wh_cumulative
                ))
        
        conn.commit()
        print(f"Solární predikce pro {tomorrow} byla úspěšně uložena")
        
    except Exception as e:
        print(f"Chyba při ukládání solární predikce: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    save_solar_forecast()