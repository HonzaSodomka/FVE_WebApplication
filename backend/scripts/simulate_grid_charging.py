import psycopg2
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def simulate_grid_charging():
    try:
        logger.info("Starting grid charging simulation")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        current_time = datetime.now().replace(second=0, microsecond=0)
        current_date = current_time.date()
        current_hour = current_time.hour

        # Debug log pro načtení ceny
        logger.info(f"Loading price data for date {current_date} hour {current_hour}")
        
        # Získáme aktuální cenu elektřiny
        cur.execute("""
            SELECT price_czk
            FROM api_pricedata 
            WHERE date = %s AND hour = %s
        """, (current_date, current_hour))
        price_data = cur.fetchone()
        
        if not price_data:
            logger.error(f"No price data for {current_date} {current_hour}:00")
            return
            
        price_mwh = price_data[0]  # Cena v Kč/MWh
        price_kwh = price_mwh / 1000  # Převod na Kč/kWh
        logger.info(f"Cena pro hodinu {current_hour} je {price_kwh:.3f}")

        # Debug log pro načtení domů
        logger.info("Loading active houses with SQL:")
        logger.info("""
            SELECT 
                id, battery_capacity, current_battery_level,
                min_battery_level, max_charging_power, charging_efficiency
            FROM api_house 
            WHERE is_active = true
        """)
        
        # Načteme aktivní domy
        cur.execute("""
            SELECT 
                id, battery_capacity, current_battery_level,
                min_battery_level, max_charging_power, charging_efficiency
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        logger.info(f"Found {len(houses)} active houses")
        
        for house in houses:
            try:
                # Debug log pro data domu
                logger.info(f"Processing house data: {house}")
                
                (house_id, battery_capacity, current_level, 
                 min_battery_level, max_charging_power, charging_eff) = house

                # Vypočteme minimální úroveň v kWh
                min_level_kwh = battery_capacity * (min_battery_level / 100)
                
                # Debug log pro stav baterie
                logger.info(f"""
                    House {house_id} battery status:
                    - Current level: {current_level}
                    - Min level: {min_level_kwh}
                    - Battery capacity: {battery_capacity}
                    - Min battery level %: {min_battery_level}
                    - Max charging power: {max_charging_power}
                    - Charging efficiency: {charging_eff}
                """)
                
                # Kontrola jestli jsme pod minimem
                if current_level < min_level_kwh:
                    # Maximální množství energie za minutu v kWh
                    max_charge_kwh = max_charging_power / 60
                    
                    # Kolik musíme dobít
                    needed_kwh = min_level_kwh - current_level
                    
                    # Kolik můžeme nabít tuto minutu
                    charge_amount = min(
                        max_charge_kwh,  # Limit nabíjení
                        needed_kwh       # Kolik chybí do minima
                    )
                    
                    # Aplikujeme účinnost nabíjení
                    actual_charge = charge_amount * (charging_eff / 100)
                    new_level = current_level + actual_charge

                    # Debug log před aktualizací baterie
                    logger.info(f"""
                        Charging calculation:
                        - Max charge per minute: {max_charge_kwh}
                        - Needed: {needed_kwh}
                        - Will charge: {charge_amount}
                        - After efficiency: {actual_charge}
                        - New level will be: {new_level}
                    """)

                    # Aktualizujeme stav baterie
                    cur.execute("""
                        UPDATE api_house 
                        SET current_battery_level = %s
                        WHERE id = %s
                    """, (new_level, house_id))
                    
                    # Spočítáme cenu nabití
                    charge_cost = actual_charge * price_kwh

                    # Debug log před uložením do ChargingData
                    logger.info(f"""
                        Will save to ChargingData:
                        - Date: {current_date}
                        - Grid charged: {actual_charge}
                        - Cost: {charge_cost}
                    """)

                    # Uložíme nabití do ChargingData
                    cur.execute("""
                        INSERT INTO api_chargingdata (house_id, date, solar_charged_kwh, grid_charged_kwh, grid_charged_cost)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (house_id, date)
                        DO UPDATE SET 
                            grid_charged_kwh = api_chargingdata.grid_charged_kwh + EXCLUDED.grid_charged_kwh,
                            grid_charged_cost = api_chargingdata.grid_charged_cost + EXCLUDED.grid_charged_cost
                    """, (
                        house_id, 
                        current_date,
                        0,                  # solar_charged_kwh
                        actual_charge,      # grid_charged_kwh
                        charge_cost         # grid_charged_cost
                    ))

                    logger.info(f"""
                        House {house_id} grid charging:
                        Time: {current_time}
                        Battery: {current_level:.2f}kWh -> {new_level:.2f}kWh
                        Min level: {min_level_kwh:.2f}kWh
                        Price: {price_kwh:.2f}Kč/kWh
                        Charged: {actual_charge*1000:.2f}Wh
                        Cost: {charge_cost:.2f}Kč
                    """)

            except Exception as e:
                logger.error(f"Error processing house {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("Grid charging simulation completed successfully")

    except Exception as e:
        logger.error(f"Grid charging simulation failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_grid_charging()