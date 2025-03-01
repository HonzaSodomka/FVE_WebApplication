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
        
        # Zjistíme, zda existuje plán nabíjení pro tuto hodinu
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
    """
    try:
        logger.info("ZAHAJUJI KOMBINOVANOU SIMULACI NABÍJENÍ (SOLÁRNÍ + SÍŤ)")
        
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Používáme naivní datetime bez timezone
        current_time = datetime.now().replace(tzinfo=None)
        current_date = current_time.date()
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Debug log pro načtení ceny
        logger.info(f"Načítám data o cenách pro datum {current_date} hodina {current_hour}")
        
        # Získáme aktuální cenu elektřiny
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
        logger.info(f"Cena pro hodinu {current_hour} je {price_kwh:.3f} Kč/kWh")

        # Najdeme čas pro solární predikci
        prediction_time = get_prediction_timestamp(current_time, conn, cur)
        
        if not prediction_time:
            logger.warning("Nelze určit časovou značku solární predikce")
            # Pokračujeme, ale nabíjení ze solárů bude 0

        # Načteme aktivní domy
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

                # Vypočteme minimální úroveň v kWh
                min_level_kwh = battery_capacity * (min_battery_level_percent / 100)
                
                # Získáme plánované nabíjení ze sítě pro tuto hodinu
                planned_grid_charging_kwh = should_charge_from_schedule(current_time, house_id, conn, cur)
                
                # Inicializace proměnných pro nabíjení
                solar_charging_wh = 0          # Kolik nabijeme ze solárů (ve Wh)
                emergency_grid_charging_kwh = 0 # Nouzové nabíjení ze sítě (v kWh)
                planned_grid_charging_minute_kwh = 0 # Plánované nabíjení ze sítě pro tuto minutu (v kWh)
                
                # Část 1: NABÍJENÍ ZE SOLÁRŮ
                if prediction_time:
                    # Získáme data o výrobě pro danou hodinu
                    cur.execute("""
                        SELECT watt_hours_period
                        FROM api_solardata
                        WHERE timestamp = %s
                    """, (prediction_time,))
                    solar_data = cur.fetchone()

                    if solar_data and solar_data[0] > 0:
                        # Vyrobená energie za hodinu v Wh (pro 20kWp)
                        period_wh = solar_data[0]

                        # Přepočet na instalovaný výkon domu
                        period_wh = period_wh * (solar_power / 20)

                        # Aplikujeme variaci
                        actual_period_wh = period_wh * solar_variation
                        
                        # Převod na minutovou výrobu
                        solar_charging_wh = actual_period_wh / 60
                    else:
                        solar_charging_wh = 0

                # Převod na kW pro kontrolu maximálního výkonu
                solar_charging_kw = solar_charging_wh / 1000
                
                # Část 2: NOUZOVÉ NABÍJENÍ ZE SÍTĚ
                # Kontrola, zda jsme pod minimem
                if current_level < min_level_kwh:
                    # Kolik musíme dobít
                    needed_kwh = (min_level_kwh - current_level)
                    
                    # Maximální výkon pro nouzové nabíjení (zbývající po solárním nabíjení)
                    remaining_power_kw = max(0, max_charging_power - solar_charging_kw)
                    
                    # Kolik můžeme nabít za minutu (v kWh)
                    emergency_grid_charging_kwh = min(
                        needed_kwh,                # Kolik potřebujeme
                        remaining_power_kw / 60    # Co zvládneme za minutu s ohledem na solár
                    )
                    
                    if emergency_grid_charging_kwh > 0:
                        logger.warning(f"""
                            Dům {house_id} NOUZOVÉ nabíjení:
                            - Stav baterie pod minimem: {current_level:.2f} kWh < {min_level_kwh:.2f} kWh
                            - Potřeba dobít: {needed_kwh:.2f} kWh
                            - Solární nabíjení: {solar_charging_kw:.4f} kW
                            - Zbývající výkon: {remaining_power_kw:.4f} kW
                            - Nouzové nabíjení: {emergency_grid_charging_kwh:.4f} kWh za minutu
                        """)

                # Část 3: PLÁNOVANÉ NABÍJENÍ ZE SÍTĚ
                if planned_grid_charging_kwh > 0:
                    # Rozdělíme plánované nabíjení na minuty
                    minute_planned_kwh = planned_grid_charging_kwh / 60
                    
                    # Aktuální využitý výkon (ze solárů a nouzového nabíjení)
                    used_power_kw = solar_charging_kw + (emergency_grid_charging_kwh * 60)  # Převod zpět na kW
                    
                    # Zbývající výkon pro plánované nabíjení
                    remaining_power_kw = max(0, max_charging_power - used_power_kw)
                    
                    # Dostupný prostor v baterii
                    available_space = battery_capacity - current_level
                    
                    # Kolik můžeme nabít
                    planned_grid_charging_minute_kwh = min(
                        minute_planned_kwh,        # Co je plánováno na minutu
                        remaining_power_kw / 60,   # Co ještě zvládneme za minutu
                        available_space            # Kolik se ještě vejde do baterie
                    )
                    
                    if planned_grid_charging_minute_kwh > 0:
                        logger.info(f"""
                            Dům {house_id} PLÁNOVANÉ nabíjení:
                            - Celkový plán pro hodinu: {planned_grid_charging_kwh:.2f} kWh
                            - Plán na minutu: {minute_planned_kwh:.4f} kWh
                            - Solární nabíjení: {solar_charging_kw:.4f} kW
                            - Nouzové nabíjení: {emergency_grid_charging_kwh:.4f} kWh
                            - Využitý výkon: {used_power_kw:.4f} kW
                            - Zbývající výkon: {remaining_power_kw:.4f} kW
                            - Plánované nabíjení: {planned_grid_charging_minute_kwh:.4f} kWh za minutu
                        """)

                # Část 4: CELKOVÉ NABÍJENÍ A APLIKACE ÚČINNOSTI
                # Celková energie pro nabíjení před započtením účinnosti
                total_charging_kwh = (solar_charging_wh / 1000) + emergency_grid_charging_kwh + planned_grid_charging_minute_kwh
                
                # Aplikujeme účinnost nabíjení - až na konci procesu!
                efficiency_factor = charging_eff / 100
                actual_charge_kwh = total_charging_kwh * efficiency_factor
                
                # Nový stav baterie
                new_level = current_level + actual_charge_kwh
                
                # Výpočet nákladů na nabíjení ze sítě
                grid_charging_kwh = emergency_grid_charging_kwh + planned_grid_charging_minute_kwh
                grid_charging_cost = grid_charging_kwh * price_kwh
                
                # Aktualizace databáze pouze pokud skutečně došlo k nabíjení
                if total_charging_kwh > 0:
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
                        (solar_charging_wh / 1000) * efficiency_factor,  # solar_charged_kwh s účinností
                        grid_charging_kwh * efficiency_factor,           # grid_charged_kwh s účinností
                        grid_charging_cost                               # grid_charged_cost
                    ))
                    
                    logger.info(f"""
                        Dům {house_id} CELKOVÉ nabíjení:
                        - Datum a čas: {current_date} {current_hour:02d}:{current_minute:02d}
                        - Ze solárů: {solar_charging_wh/1000:.4f} kWh (před účinností)
                        - Ze sítě: {grid_charging_kwh:.4f} kWh (před účinností)
                        - Celkem: {total_charging_kwh:.4f} kWh (před účinností)
                        - Učinnost: {efficiency_factor*100:.0f}%
                        - Skutečně nabito: {actual_charge_kwh:.4f} kWh
                        - Cena nabíjení ze sítě: {grid_charging_cost:.2f} Kč
                        - Stav baterie: {current_level:.2f} kWh -> {new_level:.2f} kWh
                    """)
                else:
                    logger.info(f"Dům {house_id}: Žádné nabíjení neproběhlo v čase {current_time}")

            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("KOMBINOVANÁ SIMULACE NABÍJENÍ ÚSPĚŠNĚ DOKONČENA")

    except Exception as e:
        logger.error(f"Kombinovaná simulace nabíjení selhala: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_combined_charging()