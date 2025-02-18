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
        
        weekday_data = {hour: [] for hour in range(24)}
        weekend_data = {hour: [] for hour in range(24)}

        cur.execute("""
            SELECT date, hour, consumption_wh
            FROM api_consumptiondata
            WHERE house_id = %s AND date BETWEEN %s AND %s
            ORDER BY date, hour
        """, (house_id, start_date, end_date))
        
        records = cur.fetchall()
        
        for record_date, hour, consumption in records:
            if record_date.weekday() < 5:  # Pondělí-Pátek
                weekday_data[hour].append(consumption)
            else:  # Sobota-Neděle
                weekend_data[hour].append(consumption)

        weekday_profile = {
            hour: (mean(consumptions) if consumptions else 0)
            for hour, consumptions in weekday_data.items()
        }
        
        weekend_profile = {
            hour: (mean(consumptions) if consumptions else 0)
            for hour, consumptions in weekend_data.items()
        }

        logger.info(f"""
        HISTORICKÁ ANALÝZA DOMU {house_id}:
        Období: {start_date} až {end_date}
        
        VŠEDNÍ DNY (průměrná spotřeba Wh):
        {chr(10).join(f'{str(hour).zfill(2)}:00 - {weekday_profile[hour]:6.1f} Wh' for hour in range(24))}
        
        VÍKENDY (průměrná spotřeba Wh):
        {chr(10).join(f'{str(hour).zfill(2)}:00 - {weekend_profile[hour]:6.1f} Wh' for hour in range(24))}
        """)
        
        return weekday_profile, weekend_profile

    except Exception as e:
        logger.error(f"Chyba při analýze historické spotřeby pro dům {house_id}: {str(e)}")
        raise

def plan_charging():
    """
    Hlavní funkce pro plánování nabíjení.
    Spouští se v 17:01 když máme data o cenách na další den.
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
                weekday_profile, weekend_profile = get_historical_consumption(house_id, conn, cur)
                
                # TODO: Tady budeme pokračovat s plánováním nabíjení
                # pro každý dům na základě získaných profilů
                
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