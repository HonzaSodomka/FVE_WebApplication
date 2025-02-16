import requests
from datetime import datetime, date, timedelta
import psycopg2
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',  # Stejný soubor jako používá Django
    filemode='a'  # 'a' znamená append - přidává záznamy na konec souboru
)

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
   logger.info(f"POŽADAVEK NA PREDIKCI O NABÍJENÍ Z FVE ODESLÁN NA {url}")
   response = requests.get(url, headers=headers)
   #200 = success
   if response.status_code == 200:
       logger.info("Solární předpověď úspěšně načtena z API API")
       return response.json()
   else:
       logger.error(f"API request selhal. Chybový kód: {response.status_code}")
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
       logger.info(f"Ukládám předpověď solární výroby pro den {tomorrow}")
       
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
       logger.info(f"ÚSPĚŠNĚ ULOŽENO {records_updated} SOLÁRNÍCH PŘEDPOVĚDÍ PRO {tomorrow}")
       
   except KeyError as e:
       logger.error(f"Neočekávaný formát API odpovědi: {str(e)}")
       conn.rollback()
   except psycopg2.Error as e:
       logger.error(f"Chyba databáze: {str(e)}")
       conn.rollback()
   except Exception as e:
       logger.error(f"Neočekávaná chyba při ukládání solární predikce {str(e)}")
       conn.rollback()
   finally:
       cur.close()
       conn.close()
       logger.debug("Připojení k databázi ukončeno")

if __name__ == "__main__":
   try:
       save_solar_forecast()
   except Exception as e:
       logger.error(f"Skript selhal: {str(e)}")
       raise