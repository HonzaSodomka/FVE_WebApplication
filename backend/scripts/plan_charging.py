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
        
        cur.execute("""
            WITH hourly_sums AS (
                SELECT 
                    date,
                    CAST(SUBSTRING(time FROM 1 FOR 2) AS INTEGER) as hour,
                    SUM(
                        (SELECT SUM(CAST(item->>'consumption_w' AS FLOAT)) 
                        FROM jsonb_array_elements(appliance_consumption) item)
                    ) as hour_consumption
                FROM api_consumptiondata
                WHERE house_id = %s AND date BETWEEN %s AND %s
                GROUP BY date, CAST(SUBSTRING(time FROM 1 FOR 2) AS INTEGER)
            )
            SELECT 
                hour,
                EXTRACT(DOW FROM date) NOT IN (0, 6) as is_weekday,
                hour_consumption
            FROM hourly_sums
            ORDER BY hour, date
        """, (house_id, start_date, end_date))
        
        records = cur.fetchall()
        
        weekday_data = {hour: [] for hour in range(24)}
        weekend_data = {hour: [] for hour in range(24)}
        
        for hour, is_weekday, consumption in records:
            if is_weekday:
                weekday_data[hour].append(consumption)
            else:
                weekend_data[hour].append(consumption)

        weekday_profile = {
            hour: (mean(consumptions) if consumptions else 0)
            for hour, consumptions in weekday_data.items()
        }
        
        weekend_profile = {
            hour: (mean(consumptions) if consumptions else 0)
            for hour, consumptions in weekend_data.items()
        }

        logger.info(f"Vytvořeny spotřební profily pro dům {house_id} (období {start_date} až {end_date})")
        
        return weekday_profile, weekend_profile

    except Exception as e:
        logger.error(f"Chyba při analýze historické spotřeby pro dům {house_id}: {str(e)}")
        raise

def get_spot_prices(target_date, conn, cur):
    """
    Načte spotové ceny pro daný den.
    Vrací slovník {hodina: cena_czk}
    """
    try:
        cur.execute("""
            SELECT hour, price_czk
            FROM api_pricedata
            WHERE date = %s
            ORDER BY hour
        """, (target_date,))
        
        prices = {hour: price for hour, price in cur.fetchall()}
        
        if not prices:
            raise Exception(f"Chybí data o cenách pro {target_date}")
            
        logger.info(f"Načteny spotové ceny pro {target_date}")
        return prices

    except Exception as e:
        logger.error(f"Chyba při načítání spotových cen: {str(e)}")
        raise

def get_solar_prediction(house_id, target_date, conn, cur):
    """
    Načte predikci solární výroby pro daný den a dům.
    Vrací slovník {hodina: wh}
    """
    try:
        # Načteme solární data a parametry domu
        cur.execute("""
            WITH solar_data AS (
                SELECT 
                    EXTRACT(HOUR FROM timestamp) as hour,
                    watt_hours_period as base_wh
                FROM api_solardata
                WHERE DATE(timestamp) = %s
            ),
            house_data AS (
                SELECT 
                    solar_power,
                    solar_variation
                FROM api_house
                WHERE id = %s
            )
            SELECT 
                s.hour,
                s.base_wh * (h.solar_power / 20.0) * h.solar_variation as wh
            FROM solar_data s
            CROSS JOIN house_data h
            ORDER BY s.hour
        """, (target_date, house_id))
        
        predictions = {int(hour): wh for hour, wh in cur.fetchall()}
        
        if not predictions:
            raise Exception(f"Chybí solární predikce pro {target_date}")
            
        logger.info(f"Načtena solární predikce pro dům {house_id} ({target_date})")
        return predictions

    except Exception as e:
        logger.error(f"Chyba při načítání solární predikce: {str(e)}")
        raise

def get_house_params(house_id, conn, cur):
    """
    Načte parametry domu potřebné pro plánování nabíjení.
    """
    try:
        cur.execute("""
            SELECT 
                battery_capacity,
                current_battery_level,
                min_battery_level,
                max_charging_power,
                charging_efficiency,
                risk_level
            FROM api_house
            WHERE id = %s
        """, (house_id,))
        
        (battery_capacity, current_level, min_level, 
         max_charging, efficiency, risk_level) = cur.fetchone()
        
        params = {
            'battery_capacity': battery_capacity,          # kWh
            'current_level': current_level,               # kWh
            'min_level': min_level,                      # %
            'max_charging_power': max_charging,          # kW
            'charging_efficiency': efficiency,            # %
            'risk_level': risk_level                     # LOW/MEDIUM/HIGH
        }
        
        logger.info(f"""
        Parametry domu {house_id}:
        - Baterie: {current_level:.1f}/{battery_capacity:.1f} kWh (min {min_level}%)
        - Nabíjení: max {max_charging:.1f} kW, účinnost {efficiency}%
        - Risk level: {risk_level}
        """)
        
        return params

    except Exception as e:
        logger.error(f"Chyba při načítání parametrů domu {house_id}: {str(e)}")
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

        tomorrow = date.today() + timedelta(days=1)
        is_weekend = tomorrow.weekday() >= 5
        logger.info(f"Plánování nabíjení na {tomorrow} ({'víkend' if is_weekend else 'všední den'})")

        # Načteme spotové ceny na zítřek (společné pro všechny domy)
        prices = get_spot_prices(tomorrow, conn, cur)
        logger.info(f"""
        SPOTOVÉ CENY:
        {chr(10).join(f'{str(hour).zfill(2)}:00 - {price:.2f} Kč/MWh' for hour, price in sorted(prices.items()))}
        """)

        cur.execute("SELECT id FROM api_house WHERE is_active = true")
        houses = cur.fetchall()
        logger.info(f"Načteno {len(houses)} aktivních domů")

        for (house_id,) in houses:
            try:
                logger.info(f"--------- DŮM {house_id} ---------")
                
                # Načtení všech potřebných dat
                params = get_house_params(house_id, conn, cur)
                logger.info(f"""
                PARAMETRY DOMU:
                - Baterie: {params['current_level']:.1f}/{params['battery_capacity']:.1f} kWh
                - Min. úroveň: {params['min_level']}%
                - Max. nabíjení: {params['max_charging_power']} kW
                - Účinnost: {params['charging_efficiency']}%
                - Risk level: {params['risk_level']}
                """)
                
                weekday_profile, weekend_profile = get_historical_consumption(house_id, conn, cur)
                profile = weekend_profile if is_weekend else weekday_profile
                logger.info(f"""
                OČEKÁVANÁ SPOTŘEBA:
                {chr(10).join(f'{str(hour).zfill(2)}:00 - {consumption:.1f} Wh' for hour, consumption in sorted(profile.items()))}
                """)
                
                solar_prediction = get_solar_prediction(house_id, tomorrow, conn, cur)
                logger.info(f"""
                PREDIKCE VÝROBY:
                {chr(10).join(f'{str(hour).zfill(2)}:00 - {wh:.1f} Wh' for hour, wh in sorted(solar_prediction.items()))}
                """)

                # Výpis bilance (spotřeba - výroba) pro každou hodinu
                logger.info(f"""
                BILANCE (spotřeba - výroba):
                {chr(10).join(f'{str(hour).zfill(2)}:00 - {profile[hour] - solar_prediction.get(hour, 0):.1f} Wh' for hour in range(24))}
                """)
                
            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        logger.info("PLÁNOVÁNÍ NABÍJENÍ DOKONČENO")

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