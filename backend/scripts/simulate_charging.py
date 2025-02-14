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

def simulate_charging():
    try:
        logger.info("Starting charging simulation")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Načteme aktivní domy
        cur.execute("""
            SELECT 
                id, battery_capacity, current_battery_level,
                max_charging_power, charging_efficiency, solar_variation
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        logger.info(f"Found {len(houses)} active houses")

        current_time = datetime.now().replace(second=0, microsecond=0)
        
        for house in houses:
            (house_id, battery_capacity, current_level, 
             max_charging_power, charging_eff, solar_variation) = house

            try:
                # Získáme předpověď solární výroby pro aktuální hodinu
                cur.execute("""
                    SELECT watts
                    FROM api_solardata
                    WHERE timestamp = %s
                """, (current_time,))
                solar_data = cur.fetchone()

                if not solar_data:
                    logger.warning(f"No solar prediction for house {house_id} at {current_time}")
                    continue

                predicted_watts = solar_data[0]

                # Aplikujeme variaci na predikovanou výrobu
                actual_watts = predicted_watts * solar_variation if predicted_watts else 0
                
                # Převod na minutovou výrobu v kW (z W)
                available_power = actual_watts / 1000
                
                # Za minutu můžeme vyrobit 1/60 hodinové výroby
                available_kwh = available_power / 60

                # Pokud máme solární výrobu, pokusíme se nabít baterii
                if available_kwh > 0:
                    # Omezení nabíjecího výkonu na minutu
                    max_charging_kwh = max_charging_power / 60
                    
                    # Volné místo v baterii
                    available_space = battery_capacity - current_level
                    
                    if available_space > 0:
                        # Určíme kolik energie můžeme uložit
                        charging_amount = min(
                            available_kwh,      # Solární výroba
                            max_charging_kwh,   # Limit nabíjení
                            available_space     # Místo v baterii
                        )
                        
                        # Aplikujeme účinnost nabíjení
                        actual_charge = charging_amount * (charging_eff / 100)
                        new_level = current_level + actual_charge

                        # Aktualizujeme stav baterie
                        cur.execute("""
                            UPDATE api_house 
                            SET current_battery_level = %s
                            WHERE id = %s
                        """, (new_level, house_id))

                        logger.info(f"""
                            House {house_id} solar charging:
                            Time: {current_time}
                            Solar variation: {solar_variation:.2f}
                            Predicted power: {predicted_watts:.2f}W
                            Actual power: {actual_watts:.2f}W
                            Available energy: {available_kwh*1000:.2f}Wh/min
                            Charged: {actual_charge*1000:.2f}Wh
                            Battery: {current_level:.2f}kWh -> {new_level:.2f}kWh
                        """)

            except Exception as e:
                logger.error(f"Error processing house {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("Charging simulation completed successfully")

    except Exception as e:
        logger.error(f"Charging simulation failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_charging()