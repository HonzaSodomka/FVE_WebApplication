#!/usr/bin/env python
# backend/scripts/plan_charging.py

from datetime import date, timedelta
from statistics import mean
import psycopg2
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def get_historical_consumption(house_id, conn, cur, days_back=30):
    """
    Analyzuje historickou spotřebu domu a vytvoří profily pro všední dny a víkendy.
    """
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Specificky pro 23. hodinu o víkendech
        cur.execute("""
            WITH hourly_sums AS (
                SELECT 
                    date,
                    CAST(SUBSTRING(time FROM 1 FOR 2) AS INTEGER) as hour,
                    EXTRACT(DOW FROM date) as day_of_week,
                    (SELECT SUM(CAST(item->>'consumption_w' AS FLOAT)) 
                    FROM jsonb_array_elements(appliance_consumption) item) as hour_consumption
                FROM api_consumptiondata
                WHERE 
                    house_id = %s 
                    AND date BETWEEN %s AND %s
                    AND CAST(SUBSTRING(time FROM 1 FOR 2) AS INTEGER) = 23
                    AND EXTRACT(DOW FROM date) >= 5  -- Víkend (5 = sobota, 6 = neděle)
            )
            SELECT 
                date, 
                day_of_week, 
                hour_consumption
            FROM hourly_sums
            ORDER BY date
        """, (house_id, start_date, end_date))
        
        records = cur.fetchall()
        
        # Příprava pro výpis
        weekend_consumption = []
        for record in records:
            date_val, day_of_week, consumption = record
            weekend_consumption.append({
                'date': date_val,
                'day_of_week': 'Sobota' if day_of_week == 5 else 'Neděle',
                'consumption': consumption
            })
        
        # Výpočet průměru
        if weekend_consumption:
            average_consumption = sum(
                record['consumption'] for record in weekend_consumption
            ) / len(weekend_consumption)
        else:
            average_consumption = 0
        
        # Detailed logging
        logger.info(f"""
        ANALÝZA SPOTŘEBY PRO DŮM {house_id} - 23. HODINA O VÍKENDECH:
        
        Analyzované období: {start_date} až {end_date}
        Počet nalezených záznamů: {len(weekend_consumption)}
        
        JEDNOTLIVÉ ZÁZNAMY:
        {chr(10).join(
            f"{record['date']} ({record['day_of_week']}): {record['consumption']:.2f} Wh" 
            for record in weekend_consumption
        )}
        
        PRŮMĚRNÁ SPOTŘEBA: {average_consumption:.2f} Wh
        """)
        
        return weekend_consumption, average_consumption

    except Exception as e:
        logger.error(f"Chyba při analýze historické spotřeby pro dům {house_id}: {str(e)}")
        raise

def plan_charging():
    """
    Hlavní funkce pro plánování nabíjení.
    """
    try:
        logger.info("ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Načteme všechny aktivní domy
        cur.execute("""
            SELECT id
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        
        logger.info(f"Načteno {len(houses)} aktivních domů")

        # Pro každý aktivní dům uděláme analýzu
        for (house_id,) in houses:
            try:
                # Zavolání funkce pro analýzu spotřeby
                weekend_consumption, average_consumption = get_historical_consumption(house_id, conn, cur)
                
            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        logger.info("PLÁNOVÁNÍ NABÍJENÍ ÚSPĚŠNĚ DOKONČENO")

    except Exception as e:
        logger.error(f"Chyba při plánování nabíjení: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    plan_charging()