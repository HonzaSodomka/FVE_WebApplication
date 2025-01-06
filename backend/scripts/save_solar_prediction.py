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
    
    #Volání api url s hlavičkama
    response = requests.get(url, headers=headers)
    #200 = success
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")

import requests
from datetime import datetime, date, timedelta
import psycopg2
import json
import logging

logger = logging.getLogger('api')

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
   
   #Volání api url s hlavičkama
   logger.info(f"Request for solar forecast sent to {url}")
   response = requests.get(url, headers=headers)
   #200 = success
   if response.status_code == 200:
       logger.info("Successfully fetched solar forecast from API")
       return response.json()
   else:
       logger.error(f"API request failed with status code: {response.status_code}")
       raise Exception(f"Failed to fetch data: {response.status_code}")

def save_solar_forecast():
   logger.info("Connecting to database")
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
       logger.info(f"Saving solar forecast for {tomorrow}")
       
       records_updated = 0
       # Najde timestamp v první části json dat (u wh_period) a když splní že je pro zítřek, vytáhne i zbytek dat a uloží do db
       for timestamp_str, wh_period in data['result']['watt_hours_period'].items():
           # Kontrola jestli je záznam pro zítřejší den
           if timestamp_str.startswith(tomorrow):
               timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
               
               #Vytáhne data pro zvolený den
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
               records_updated += 1
       
       conn.commit()
       logger.info(f"Successfully saved {records_updated} solar forecast records for {tomorrow}")
       
   except KeyError as e:
       logger.error(f"Unexpected API response format: {str(e)}")
       conn.rollback()
   except psycopg2.Error as e:
       logger.error(f"Database error: {str(e)}")
       conn.rollback()
   except Exception as e:
       logger.error(f"Unexpected error saving solar forecast: {str(e)}")
       conn.rollback()
   finally:
       cur.close()
       conn.close()
       logger.debug("Database connection closed")

if __name__ == "__main__":
   try:
       save_solar_forecast()
   except Exception as e:
       logger.error(f"Script failed: {str(e)}")
       raise

if __name__ == "__main__":
    save_solar_forecast()