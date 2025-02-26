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

def simulate_grid_charging():
    try:
        logger.info("ZAHAJUJI SIMULACI NABÍJENÍ ZE SÍTĚ")
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
        
        # Načteme aktivní domy
        cur.execute("""
            SELECT 
                id, battery_capacity, current_battery_level,
                min_battery_level, max_charging_power, charging_efficiency
            FROM api_house 
            WHERE is_active = true
        """)
        houses = cur.fetchall()
        logger.info(f"Nalezeno {len(houses)} aktivních domů")
        
        for house in houses:
            try:
                (house_id, battery_capacity, current_level, 
                 min_battery_level_percent, max_charging_power, charging_eff) = house

                # Vypočteme minimální úroveň v kWh
                min_level_kwh = battery_capacity * (min_battery_level_percent / 100)
                
                # Inicializace proměnných pro nabíjení
                emergency_charged_kwh = 0
                planned_charged_kwh = 0
                
                # 1. KONTROLA NOUZOVÉHO NABÍJENÍ (pokud jsme pod minimem)
                if current_level < min_level_kwh:
                    # Maximální množství energie za minutu v kWh
                    max_charge_kwh = max_charging_power / 60
                    
                    # Kolik musíme dobít (započítáme ztráty z účinnosti)
                    needed_kwh = (min_level_kwh - current_level) / (charging_eff / 100)
                    
                    # Kolik můžeme nabít tuto minutu
                    charge_amount = min(
                        max_charge_kwh,  # Limit nabíjení
                        needed_kwh       # Kolik chybí do minima (včetně ztrát)
                    )
                    
                    # Aplikujeme účinnost nabíjení
                    actual_charge = charge_amount * (charging_eff / 100)
                    emergency_charged_kwh = actual_charge
                    new_level = current_level + actual_charge

                    logger.warning(f"""
                        Dům {house_id} NOUZOVÉ nabíjení:
                        - Stav baterie pod minimem: {current_level:.2f} kWh < {min_level_kwh:.2f} kWh
                        - Potřeba dobít: {needed_kwh:.2f} kWh
                        - Nabito: {charge_amount:.2f} kWh (se ztrátami)
                        - Reálný přírůstek: {actual_charge:.2f} kWh
                        - Nový stav baterie: {new_level:.2f} kWh
                    """)
                    
                    # Aktualizujeme stav baterie po nouzovém nabíjení
                    current_level = new_level
                
                # 2. KONTROLA PLÁNOVANÉHO NABÍJENÍ
                planned_charging_kwh = should_charge_from_schedule(current_time, house_id, conn, cur)
                
                if planned_charging_kwh > 0:
                    # Rozdělíme plánované nabíjení na minuty
                    minute_planned_kwh = planned_charging_kwh / 60
                    
                    # Omezení nabíjecího výkonu za minutu
                    max_charge_kwh = max_charging_power / 60
                    
                    # Dostupný prostor v baterii
                    available_space = battery_capacity - current_level
                    
                    # Kolik můžeme nabít (se ztrátami)
                    charge_amount = min(
                        minute_planned_kwh,
                        max_charge_kwh,
                        available_space / (charging_eff / 100)
                    )
                    
                    # Aplikujeme účinnost nabíjení
                    actual_charge = charge_amount * (charging_eff / 100)
                    planned_charged_kwh = actual_charge
                    new_level = current_level + actual_charge
                    
                    logger.info(f"""
                        Dům {house_id} PLÁNOVANÉ nabíjení:
                        - Celkový plán pro hodinu: {planned_charging_kwh:.2f} kWh
                        - Plán na minutu: {minute_planned_kwh:.4f} kWh
                        - Nabito: {charge_amount:.4f} kWh (se ztrátami)
                        - Reálný přírůstek: {actual_charge:.4f} kWh
                        - Stav baterie: {current_level:.2f} kWh -> {new_level:.2f} kWh
                    """)
                    
                    # Aktualizujeme stav baterie po plánovaném nabíjení
                    current_level = new_level
                
                # 3. VÝPOČET CELKOVÝCH NÁKLADŮ A AKTUALIZACE DATABÁZE
                total_charged_kwh = emergency_charged_kwh + planned_charged_kwh
                
                if total_charged_kwh > 0:
                    # Výpočet nákladů
                    total_cost = total_charged_kwh * price_kwh
                    
                    # Aktualizace stavu baterie
                    cur.execute("""
                        UPDATE api_house 
                        SET current_battery_level = %s
                        WHERE id = %s
                    """, (current_level, house_id))
                    
                    # Záznam do ChargingData
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
                        0,                      # solar_charged_kwh (nemění se)
                        total_charged_kwh,      # grid_charged_kwh
                        total_cost              # grid_charged_cost
                    ))
                    
                    logger.info(f"""
                        Dům {house_id} SOUHRN nabíjení ze sítě:
                        - Nouzové: {emergency_charged_kwh:.4f} kWh
                        - Plánované: {planned_charged_kwh:.4f} kWh
                        - Celkem: {total_charged_kwh:.4f} kWh
                        - Cena: {total_cost:.2f} Kč
                        - Konečný stav baterie: {current_level:.2f} kWh
                    """)
                else:
                    logger.info(f"Dům {house_id}: Žádné nabíjení ze sítě neproběhlo")

            except Exception as e:
                logger.error(f"Chyba při zpracování domu {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("SIMULACE NABÍJENÍ ZE SÍTĚ ÚSPĚŠNĚ DOKONČENA")

    except Exception as e:
        logger.error(f"Simulace nabíjení ze sítě selhala: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    simulate_grid_charging()