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
    """
    Najde správný timestamp pro solární predikci nebo vrátí None pokud je mimo rozsah dat.
    
    Args:
        current_time: Aktuální čas
        conn: Databázové spojení
        cur: Kurzor k databázi
        
    Returns:
        datetime nebo None: Časová značka pro predikci nebo None pokud je mimo rozsah
    """
    today = current_time.date()
    
    # Načtení prvního a posledního záznamu pro dnešek
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
        
    # Kontrola rozsahu simulace
    if current_time < first_record[0].replace(tzinfo=None) or current_time > last_record[0].replace(tzinfo=None):
        logger.info(f"Aktuální čas {current_time} je mimo čas simulace nabíjení ze solárů")
        return None
        
    # Pro čas po posledním hodinovém záznamu použití posledního dostupného záznamu dne
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

def should_charge_from_schedule(current_time, house_id, conn, cur):
    """
    Zjistí, zda má být v aktuální hodině prováděno plánované nabíjení
    a vrátí plánované množství energie, které se má nabít.
    
    Args:
        current_time: Aktuální čas
        house_id: ID domu
        conn: Databázové spojení
        cur: Kurzor k databázi
        
    Returns:
        Float: Množství energie v kWh, které se má nabít (0 pokud nemá být nabíjení)
    """
    try:
        current_date = current_time.date()
        current_hour = current_time.hour
        
        # Kontrola plánu nabíjení pro tuto hodinu
        cur.execute("""
            SELECT planned_charging_kwh
            FROM api_chargingschedule
            WHERE house_id = %s AND date = %s AND hour = %s
        """, (house_id, current_date, current_hour))
        
        schedule = cur.fetchone()
        if schedule:
            return schedule[0]
        return 0
    except Exception as e:
        logger.error(f"Chyba při zjišťování plánu nabíjení pro dům {house_id}: {str(e)}")
        return 0

def simulate_combined_charging():
    """
    Kombinovaná funkce pro simulaci nabíjení ze solárů a ze sítě.
    Hlídá maximální nabíjecí výkon a správné aplikování účinnosti.
    Prioritizuje: 1) solární nabíjení, 2) plánované nabíjení, 3) nouzové nabíjení
    """
    try:
        logger.info("ZAHÁJENÍ KOMBINOVANÉ SIMULACE NABÍJENÍ")
        
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Použití datetime bez timezone
        current_time = datetime.now().replace(tzinfo=None)
        current_date = current_time.date()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Načtení aktuální ceny elektřiny
        cur.execute("""
            SELECT price_czk
            FROM api_pricedata 
            WHERE date = %s AND hour = %s
        """, (current_date, current_hour))
        price_data = cur.fetchone()
        
        if not price_data:
            logger.error(f"Data o cenách nenalezena pro {current_date} {current_hour}:00")
            return
            
        price_mwh = price_data[0]  # Cena v Kč/MWh
        price_kwh = price_mwh / 1000  # Převod na Kč/kWh

        # Zjištění času pro solární predikci
        prediction_time = get_prediction_timestamp(current_time, conn, cur)
        
        if not prediction_time:
            logger.warning("Nelze určit časovou značku solární predikce")
            # Pokračování, ale nabíjení ze solárů bude 0

        # Načtení aktivních domů
        cur.execute("""
            SELECT 
                id, battery_capacity, current_battery_level,
                min_battery_level, max_charging_power, charging_efficiency,
                solar_variation, solar_power
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        logger.info(f"Nalezeno {len(houses)} aktivních domů")
        
        for house in houses:
            try:
                (house_id, battery_capacity, current_level, 
                 min_battery_level_percent, max_charging_power, charging_eff,
                 solar_variation, solar_power) = house

                # Výpočet minimální úrovně v kWh
                min_level_kwh = battery_capacity * (min_battery_level_percent / 100)
                
                # Získání plánovaného nabíjení ze sítě pro tuto hodinu
                planned_grid_charging_kwh = should_charge_from_schedule(current_time, house_id, conn, cur)
                
                # Inicializace proměnných pro nabíjení
                solar_charging_wh = 0          # Nabíjení ze solárů (ve Wh)
                emergency_grid_charging_kwh = 0 # Nouzové nabíjení ze sítě (v kWh)
                planned_grid_charging_minute_kwh = 0 # Plánované nabíjení ze sítě pro tuto minutu (v kWh)
                
                # Část 1: NABÍJENÍ ZE SOLÁRŮ
                if prediction_time:
                    # Získání dat o výrobě pro danou hodinu
                    cur.execute("""
                        SELECT watt_hours_period
                        FROM api_solardata
                        WHERE timestamp = %s
                    """, (prediction_time,))
                    solar_data = cur.fetchone()

                    if solar_data and solar_data[0] > 0:
                        period_wh = solar_data[0]

                        # Přepočet na instalovaný výkon domu
                        period_wh = period_wh * (solar_power / 20)

                        # Aplikace variace
                        actual_period_wh = period_wh * solar_variation
                        
                        # Převod na minutovou výrobu
                        solar_charging_wh = actual_period_wh / 60
                    else:
                        solar_charging_wh = 0

                # Převod na kW pro kontrolu maximálního výkonu
                solar_charging_kw = solar_charging_wh / 1000
                
                # Část 2: PLÁNOVANÉ NABÍJENÍ ZE SÍTĚ
                if planned_grid_charging_kwh > 0:
                    # Rozdělení plánovaného nabíjení na minuty
                    minute_planned_kwh = planned_grid_charging_kwh / 60
                    
                    # Aktuální využitý výkon (ze solárů)
                    used_power_kw = solar_charging_kw
                    
                    # Zbývající výkon pro plánované nabíjení
                    remaining_power_kw = max(0, max_charging_power - used_power_kw)
                    
                    # Dostupný prostor v baterii
                    available_space = battery_capacity - current_level
                    
                    # Výpočet možného nabíjení
                    planned_grid_charging_minute_kwh = min(
                        minute_planned_kwh,        # Co je plánováno na minutu
                        remaining_power_kw / 60,   # Co ještě zvládneme za minutu
                        available_space            # Kolik se ještě vejde do baterie
                    )
                
                # Část 3: NOUZOVÉ NABÍJENÍ ZE SÍTĚ
                # Výpočet očekávané úrovně po solárním a plánovaném nabíjení
                efficiency_factor = charging_eff / 100
                estimated_level_after_planned = current_level + (solar_charging_wh / 1000 * efficiency_factor) + (planned_grid_charging_minute_kwh * efficiency_factor)
                
                if estimated_level_after_planned < min_level_kwh:
                    # Výpočet potřebného dobití
                    needed_kwh = (min_level_kwh - estimated_level_after_planned)
                    
                    # Maximální výkon pro nouzové nabíjení (zbývající po solárním a plánovaném nabíjení)
                    used_power_kw = solar_charging_kw + (planned_grid_charging_minute_kwh * 60)  # Převod zpět na kW
                    remaining_power_kw = max(0, max_charging_power - used_power_kw)
                    
                    # Výpočet možného nouzového nabíjení za minutu (v kWh)
                    emergency_grid_charging_kwh = min(
                        needed_kwh / efficiency_factor,   # Kolik potřebujeme (s účinností)
                        remaining_power_kw / 60           # Co zvládneme za minutu s ohledem na solár a plánované
                    )
                    
                    if emergency_grid_charging_kwh > 0:
                        logger.warning(f"Dům {house_id}: Aktivováno nouzové nabíjení ({emergency_grid_charging_kwh:.4f} kWh)")

                # Část 4: CELKOVÉ NABÍJENÍ A APLIKACE ÚČINNOSTI
                # Ověření využitelné solární energie
                solar_charging_kwh = solar_charging_wh / 1000
                available_capacity = battery_capacity - current_level
                
                # První priorita - solární energie (s aplikací účinnosti)
                usable_solar_kwh = min(solar_charging_kwh, available_capacity / efficiency_factor)
                actual_solar_charge_kwh = usable_solar_kwh * efficiency_factor
                
                # Aktualizace dostupné kapacity po solárním nabíjení
                remaining_capacity = battery_capacity - (current_level + actual_solar_charge_kwh)
                
                # Druhá priorita - plánované nabíjení ze sítě
                if planned_grid_charging_minute_kwh > 0:
                    # Ověření využitelného plánovaného nabíjení
                    usable_planned_kwh = min(planned_grid_charging_minute_kwh, remaining_capacity / efficiency_factor)
                    actual_planned_charge_kwh = usable_planned_kwh * efficiency_factor
                    # Aktualizace dostupné kapacity
                    remaining_capacity -= actual_planned_charge_kwh
                else:
                    usable_planned_kwh = 0
                    actual_planned_charge_kwh = 0
                
                # Třetí priorita - nouzové nabíjení ze sítě
                if emergency_grid_charging_kwh > 0:
                    # Ověření využitelného nouzového nabíjení
                    usable_emergency_kwh = min(emergency_grid_charging_kwh, remaining_capacity / efficiency_factor)
                    actual_emergency_charge_kwh = usable_emergency_kwh * efficiency_factor
                else:
                    usable_emergency_kwh = 0
                    actual_emergency_charge_kwh = 0
                
                # Celkové dobití v této iteraci (s aplikovanou účinností)
                total_actual_charge_kwh = actual_solar_charge_kwh + actual_planned_charge_kwh + actual_emergency_charge_kwh
                
                # Nový stav baterie
                new_level = current_level + total_actual_charge_kwh
                
                # Celková energie ze sítě a náklady
                grid_charging_kwh = usable_planned_kwh + usable_emergency_kwh
                grid_charging_cost = grid_charging_kwh * price_kwh
                
                # Aktualizace databáze pouze pokud došlo k nabíjení
                if total_actual_charge_kwh > 0:
                    # Aktualizace stavu baterie
                    cur.execute("""
                        UPDATE api_house 
                        SET current_battery_level = %s
                        WHERE id = %s
                    """, (new_level, house_id))
                    
                    # Záznam do ChargingData
                    cur.execute("""
                        INSERT INTO api_chargingdata (house_id, date, solar_charged_kwh, grid_charged_kwh, grid_charged_cost)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (house_id, date)
                        DO UPDATE SET 
                            solar_charged_kwh = api_chargingdata.solar_charged_kwh + EXCLUDED.solar_charged_kwh,
                            grid_charged_kwh = api_chargingdata.grid_charged_kwh + EXCLUDED.grid_charged_kwh,
                            grid_charged_cost = api_chargingdata.grid_charged_cost + EXCLUDED.grid_charged_cost
                    """, (
                        house_id, 
                        current_date,
                        actual_solar_charge_kwh,
                        actual_planned_charge_kwh + actual_emergency_charge_kwh,
                        grid_charging_cost
                    ))
                    
                    logger.info(f"Dům {house_id}: Nabito celkem {total_actual_charge_kwh:.4f} kWh, baterie {new_level:.2f} kWh ({new_level/battery_capacity*100:.1f}%)")

            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("SIMULACE NABÍJENÍ DOKONČENA")

    except Exception as e:
        logger.error(f"Simulace nabíjení selhala: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            
if __name__ == "__main__":
    simulate_combined_charging()