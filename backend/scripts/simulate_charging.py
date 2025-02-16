import psycopg2
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def get_prediction_timestamp(current_time, conn, cur):
    """Najde správný timestamp pro predikci nebo vrátí None pokud jsme mimo rozsah dat"""
    today = current_time.date()
    
    # Najdeme první a poslední záznam pro dnešek
    cur.execute("""
        SELECT timestamp 
        FROM api_solardata 
        WHERE DATE(timestamp) = %s
        ORDER BY timestamp ASC 
        LIMIT 1
    """, (today,))
    first_record = cur.fetchone()
    
    cur.execute("""
        SELECT timestamp 
        FROM api_solardata 
        WHERE DATE(timestamp) = %s
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (today,))
    last_record = cur.fetchone()
    
    if not first_record or not last_record:
        return None
        
    # Kontrola jestli jsme v rozsahu simulace
    if current_time < first_record[0].replace(tzinfo=None) or current_time > last_record[0].replace(tzinfo=None):
        logger.info(f"Aktuální čas {current_time} je mimo čas simulace nabíjení ze solárů {first_record[0]} - {last_record[0]}")
        return None
        
    # Pro čas po posledním hodinovém záznamu použijeme poslední dostupný záznam dne
    next_hour = (current_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    cur.execute("""
        SELECT timestamp 
        FROM api_solardata 
        WHERE DATE(timestamp) = %s
        AND timestamp >= %s
        ORDER BY timestamp ASC 
        LIMIT 1
    """, (today, next_hour))
    next_record = cur.fetchone()
    
    return next_record[0] if next_record else last_record[0]

def simulate_charging():
    try:
        logger.info("ZAHAJUJI SIMULACI NABÍJENÍ ZE SOLÁRŮ")
        
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Používáme naivní datetime bez timezone
        current_time = datetime.now().replace(tzinfo=None)
        prediction_time = get_prediction_timestamp(current_time, conn, cur)
        
        if not prediction_time:
            logger.error("Nelze určit časovou značku predikce")
            return
            
        logger.info(f"Aktuální čas: {current_time}, používá se predikce pro: {prediction_time}h")

        # Načteme aktivní domy
        cur.execute("""
            SELECT 
                id, battery_capacity, current_battery_level,
                max_charging_power, charging_efficiency, solar_variation,
                solar_power
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        logger.info(f"Nalezeno {len(houses)} aktivních domů")
        
        for house in houses:
            (house_id, battery_capacity, current_level, 
             max_charging_power, charging_eff, solar_variation,
             solar_power) = house

            try:
                # Získáme data o výrobě pro danou hodinu
                cur.execute("""
                    SELECT watt_hours_period
                    FROM api_solardata
                    WHERE timestamp = %s
                """, (prediction_time,))
                solar_data = cur.fetchone()

                if not solar_data:
                    logger.warning(f"Žádná solární data pro dům {house_id} v čase {prediction_time}")
                    continue

                # Vyrobená energie za hodinu v Wh (pro 20kWp)
                period_wh = solar_data[0]

                # Přepočet na instalovaný výkon domu
                period_wh = period_wh * (solar_power / 20)

                # Aplikujeme variaci
                actual_period_wh = period_wh * solar_variation if period_wh else 0
                
                # Převod na minutovou výrobu
                available_wh = actual_period_wh / 60

                # Pokud máme výrobu, pokusíme se nabít baterii
                if available_wh > 0:
                    # Omezení nabíjecího výkonu na minutu
                    max_charging_wh = (max_charging_power * 1000) / 60
                    
                    # Volné místo v baterii (Wh)
                    available_space_wh = (battery_capacity - current_level) * 1000
                    
                    if available_space_wh > 0:
                        # Určíme kolik energie můžeme uložit (Wh)
                        charging_amount_wh = min(
                            available_wh,         # Solární výroba
                            max_charging_wh,      # Limit nabíjení
                            available_space_wh    # Místo v baterii
                        )
                        
                        # Aplikujeme účinnost nabíjení
                        actual_charge_wh = charging_amount_wh * (charging_eff / 100)
                        
                        # Převod na kWh pro uložení
                        new_level = current_level + (actual_charge_wh / 1000)

                        # Aktualizujeme stav baterie
                        cur.execute("""
                            UPDATE api_house 
                            SET current_battery_level = %s
                            WHERE id = %s
                        """, (new_level, house_id))

                        cur.execute("""
                            INSERT INTO api_chargingdata (house_id, date, solar_charged_kwh, grid_charged_kwh, grid_charged_cost)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (house_id, date)
                            DO UPDATE SET solar_charged_kwh = api_chargingdata.solar_charged_kwh + EXCLUDED.solar_charged_kwh
                        """, (
                            house_id, 
                            current_time.date(),
                            actual_charge_wh / 1000,  # solar_charged_kwh
                            0,                        
                            0                         
                        ))

                        logger.info(f"""
                            Dům {house_id} solární nabíjení:
                            Čas: {current_time} (predikce {prediction_time})
                            Výkon solárů: {solar_power}kWp
                            Variace: {solar_variation:.2f}
                            Energie za hodinu bez variace: {period_wh:.2f}Wh
                            Energie za hodinu s variací: {actual_period_wh:.2f}Wh
                            Vyrobeno: {available_wh:.2f}Wh
                            Reálně dobito: {actual_charge_wh:.2f}Wh
                            Baterie: {current_level:.2f}kWh -> {new_level:.2f}kWh
                        """)

            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("SIMULACE DOBÍJENÍ ZE SOLÁRŮ ÚSPĚŠNĚ DOKONČENA")

    except Exception as e:
        logger.error(f"Simulace dobíjení ze solárlů selhala: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_charging()