import psycopg2
import logging
from datetime import datetime, timedelta
import pulp
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def get_active_houses():
    """Získá seznam ID aktivních domů"""
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id 
            FROM api_house 
            WHERE is_active = true
        """)
        
        active_houses = [row[0] for row in cur.fetchall()]
        logger.info(f"NAČÍTÁNÍ AKTIVNÍCH DOMŮ: Nalezeno {len(active_houses)} domů")
        
        return active_houses
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ AKTIVNÍCH DOMŮ: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_price_data(current_hour, have_tomorrow_prices=False):
    """
    Získá data o cenách elektřiny s ohledem na dostupnost dat o zítřejších cenách
    
    Args:
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Slovník s cenami elektřiny pro aktuální a případně i následující den
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)

        # Upravíme dotaz podle dostupnosti dat o zítřejších cenách
        if have_tomorrow_prices:
            # Máme data na zítřek, načteme hodiny od aktuální až do konce zítřka
            cur.execute("""
                SELECT date, hour, price_czk 
                FROM api_pricedata 
                WHERE (date = %s AND hour >= %s) OR date = %s
                ORDER BY date, hour
            """, [today, current_hour, tomorrow])
        else:
            # Nemáme data na zítřek, načteme jen hodiny od aktuální do konce dneška
            cur.execute("""
                SELECT date, hour, price_czk 
                FROM api_pricedata 
                WHERE date = %s AND hour >= %s
                ORDER BY date, hour
            """, [today, current_hour])
        
        # Vrátíme jednoduché pole cen pro použití v LP
        prices = []
        rows = cur.fetchall()
        
        for date, hour, price in rows:
            prices.append(price / 1000)  # Převod z Kč/MWh na Kč/kWh
            
        logger.info(f"NAČÍTÁNÍ CEN: Načteno {len(rows)} cenových záznamů")
        
        if not rows:
            logger.warning("NAČÍTÁNÍ CEN: Žádné cenové záznamy nenalezeny")
        
        return prices
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ CEN: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_house_data(house_id):
    """Získá data o domu podle ID"""
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                risk_level,
                solar_power,
                battery_capacity,
                current_battery_level,
                min_battery_level,
                max_charging_power,
                charging_efficiency
            FROM api_house 
            WHERE id = %s
        """, [house_id])
        
        row = cur.fetchone()
        if row:
            house_data = {
                'risk_level': row[0],
                'solar_power': row[1],
                'battery_capacity': row[2],
                'current_battery_level': row[3],
                'min_battery_level': row[4],
                'max_charging_power': row[5],
                'charging_efficiency': row[6]
            }
            logger.info(f"NAČÍTÁNÍ DAT DOMU {house_id}: Data úspěšně načtena")
            return house_data
        else:
            logger.error(f"NAČÍTÁNÍ DAT DOMU {house_id}: Dům nenalezen")
            return None
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ DAT DOMU {house_id}: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_solar_prediction(house_power, charging_efficiency, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď solární výroby a upraví ji podle výkonu domu a účinnosti nabíjení
    
    Args:
        house_power: Výkon solárních panelů v kWp
        charging_efficiency: Účinnost nabíjení v procentech
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Pole s predikovanou solární výrobou (v kWh) pro každou hodinu v plánovacím horizontu
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)

        # Upravíme dotaz podle dostupnosti dat o zítřejších cenách
        if have_tomorrow_prices:
            # Máme data na zítřek, načteme hodiny od aktuální až do konce zítřka
            cur.execute("""
                SELECT timestamp, watt_hours_period
                FROM api_solardata 
                WHERE (DATE(timestamp) = %s AND EXTRACT(HOUR FROM timestamp) >= %s) 
                   OR DATE(timestamp) = %s
                ORDER BY timestamp
            """, [today, current_hour, tomorrow])
        else:
            # Nemáme data na zítřek, načteme jen hodiny od aktuální do konce dneška
            cur.execute("""
                SELECT timestamp, watt_hours_period
                FROM api_solardata 
                WHERE DATE(timestamp) = %s AND EXTRACT(HOUR FROM timestamp) >= %s
                ORDER BY timestamp
            """, [today, current_hour])
        
        rows = cur.fetchall()
        
        # Pro debugging vytiskni získaná data
        print(f"Načteno {len(rows)} záznamů predikce solární výroby:")
        for timestamp, wh in rows:
            print(f"{timestamp}, {wh}")
            
        # Přepočítací faktory
        power_ratio = house_power / 20  # Základní predikce je na 20kWp
        efficiency_factor = charging_efficiency / 100
        
        # Zjistíme, kolik hodin máme v plánovacím horizontu
        n_hours = len(get_price_data(current_hour, have_tomorrow_prices))
        
        # Inicializujeme prázdné pole pro všechny hodiny - výchozí hodnota 0
        solar_production = [0.0] * n_hours
        
        # Mapování záznamů na hodiny v plánovacím horizontu
        for timestamp, wh in rows:
            # Určení relativní hodiny v plánovacím horizontu
            if timestamp.date() == today:
                # Pro dnešní den, odečteme aktuální hodinu
                hour_index = timestamp.hour - current_hour
            else:
                # Pro zítřejší den, přičteme počet zbývajících hodin dneška
                hour_index = (24 - current_hour) + timestamp.hour
                
            # Kontrola, zda index je v platném rozsahu
            if 0 <= hour_index < n_hours:
                # Upravená výroba
                adjusted_wh = wh * power_ratio * efficiency_factor / 1000  # Převod Wh na kWh
                solar_production[hour_index] = adjusted_wh
        
        logger.info(f"NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Vytvořena předpověď pro {n_hours} hodin")
        
        return solar_production
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: {str(e)}")
        # V případě chyby, vracíme nulové pole o stejné délce jako je počet cen
        return [0.0] * len(get_price_data(current_hour, have_tomorrow_prices))
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_consumption_prediction(house_id, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď spotřeby domu na základě historických dat
    
    Args:
        house_id: ID domu
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Pole s predikovanou spotřebou (v kWh) pro každou hodinu v plánovacím horizontu
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)
        
        # Zjistíme typ dnů (víkend/všední)
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        # Načteme historická data za posledních 30 dní
        start_date = today - timedelta(days=30)
        
        # SQL dotaz pro získání průměrných hodinových spotřeb podle typu dne
        cur.execute("""
            WITH consumption_items AS (
                SELECT 
                    date,
                    time,
                    (items->>'consumption_w')::float as consumption_w
                FROM api_consumptiondata,
                LATERAL jsonb_array_elements(appliance_consumption) items
                WHERE house_id = %s 
                    AND date >= %s
            ),
            hourly_consumption AS (
                SELECT 
                    date,
                    EXTRACT(HOUR FROM time::time) as hour,
                    EXTRACT(DOW FROM date) as day_of_week,
                    SUM(consumption_w) as total_wh
                FROM consumption_items
                GROUP BY date, EXTRACT(HOUR FROM time::time)
                ORDER BY date, hour
            )
            SELECT 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END as day_type,
                AVG(total_wh) as avg_consumption
            FROM hourly_consumption
            GROUP BY 
                hour,
                CASE WHEN day_of_week IN (0, 6) THEN 'weekend' ELSE 'weekday' END
            ORDER BY day_type, hour
        """, [house_id, start_date])
        
        rows = cur.fetchall()
        
        # Průměrná spotřeba podle typů dnů
        averages = {
            'weekday': {},
            'weekend': {}
        }
        
        for hour, day_type, avg_consumption in rows:
            averages[day_type][int(hour)] = avg_consumption
        
        # Vytvoříme pole se spotřebami po hodinách
        consumption = []
        
        # Pro dnešek od aktuální hodiny
        today_type = 'weekend' if is_today_weekend else 'weekday'
        for hour in range(current_hour, 24):
            consumption_wh = averages[today_type].get(hour, 0)
            consumption.append(consumption_wh / 1000)  # Převod na kWh
            
        # Pro zítřek všechny hodiny, jen pokud máme ceny na zítřek
        if have_tomorrow_prices:
            tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
            for hour in range(24):
                consumption_wh = averages[tomorrow_type].get(hour, 0)
                consumption.append(consumption_wh / 1000)  # Převod na kWh
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return consumption
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        # V případě chyby, vracíme defaultní spotřeby o stejné délce jako je počet cen
        return [0.2] * len(get_price_data(current_hour, have_tomorrow_prices))
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def optimize_charging_lp(house_id, house_data, solar_production, consumption, prices):
    """
    Optimalizace plánování nabíjení pomocí lineárního programování.
    
    Args:
        house_id: ID domu
        house_data: Dictionary s parametry domu
        solar_production: Pole s predikcí solární výroby (kWh) po hodinách
        consumption: Pole s predikcí spotřeby (kWh) po hodinách
        prices: Pole s cenami elektřiny (Kč/kWh) po hodinách
    
    Returns:
        Seznam s plány nabíjení po hodinách
    """
    try:
        # Ošetření vstupů - zajištění shodné délky polí
        n_hours = min(len(solar_production), len(consumption), len(prices))
        solar_production = solar_production[:n_hours]
        consumption = consumption[:n_hours]
        prices = prices[:n_hours]

        # Parametry baterie
        battery_capacity = house_data['battery_capacity']
        min_battery_level_pct = house_data['min_battery_level']
        min_battery_level = battery_capacity * (min_battery_level_pct / 100)  # Převod % na kWh
        current_level = house_data['current_battery_level']
        charging_efficiency = house_data['charging_efficiency'] / 100
        max_charging_power = house_data['max_charging_power']
        
        # Stanovení efektivního minima podle risk_level - jako fixní procenta kapacity
        risk_levels = {
            'LOW': 50,     # Konzervativní přístup - 50% kapacity
            'MEDIUM': 25,  # Vyvážený přístup - 25% kapacity
            'HIGH': 10     # Agresivní přístup - 10% kapacity
        }
        
        # Efektivní minimální úroveň (přímé procento z kapacity)
        effective_min_percent = risk_levels.get(house_data['risk_level'], 25)
        effective_min_level = battery_capacity * (effective_min_percent / 100)
        
        # Vytvoření LP problému
        prob = pulp.LpProblem(f"BatteryCharging_{house_id}", pulp.LpMinimize)
        
        # Proměnné: množství nabíjení v každé hodině
        charging = [pulp.LpVariable(f"charging_{h}", 0, max_charging_power) for h in range(n_hours)]
        
        # Proměnné: stav baterie na konci každé hodiny
        battery_level = [pulp.LpVariable(f"level_{h}", min_battery_level, battery_capacity) for h in range(n_hours)]
        
        # Slabá omezení pro efektivní minimum
        min_violations = [pulp.LpVariable(f"min_viol_{h}", 0, None) for h in range(n_hours)]
        
        # Cílová funkce: minimalizace nákladů + penalizace za porušení efektivního minima
        high_penalty = max(prices) * 10  # Vysoká penalizace za porušení efektivního minima
        
        # Kombinovaná cílová funkce
        prob += (
            pulp.lpSum([charging[h] * prices[h] for h in range(n_hours)]) + 
            pulp.lpSum([min_violations[h] * high_penalty for h in range(n_hours)])
        )
        
        # Počáteční stav baterie
        # balance = solar_production[0] - consumption[0] + charging[0] * charging_efficiency
        balance = (solar_production[0] if 0 < len(solar_production) else 0) - \
                 (consumption[0] if 0 < len(consumption) else 0) + \
                 charging[0] * charging_efficiency
        prob += battery_level[0] == current_level + balance
        
        # Vývoj stavu baterie
        for h in range(1, n_hours):
            balance = solar_production[h] - consumption[h] + charging[h] * charging_efficiency
            prob += battery_level[h] == battery_level[h-1] + balance
        
        # Omezení pro efektivní minimum (slabé omezení s penalizací)
        for h in range(n_hours):
            prob += battery_level[h] + min_violations[h] >= effective_min_level
        
        # Tvrdé omezení pro absolutní minimum
        for h in range(n_hours):
            prob += battery_level[h] >= min_battery_level
        
        # Vyřešení problému
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        
        # Kontrola, zda bylo nalezeno řešení
        if pulp.LpStatus[prob.status] != 'Optimal':
            logger.warning(f"Optimalizace pro dům {house_id} nenalezla optimální řešení: {pulp.LpStatus[prob.status]}")
            return fallback_charging_plan(house_id, house_data, solar_production, consumption, prices)
            
        # Extrakce výsledků
        charging_plan = []
        for h in range(n_hours):
            amount = pulp.value(charging[h])
            # Zaokrouhlení na 2 desetinná místa a odstranění velmi malých hodnot
            amount = round(max(0, amount), 2)
            if amount < 0.01:  # Ignorujeme zanedbatelně malé nabíjení
                amount = 0
            charging_plan.append({
                'hour': h,
                'planned_charging_kwh': amount
            })
        
        # Výpis výsledného plánu pro debugging
        logger.info(f"OPTIMALIZACE NABÍJENÍ LP: Dům {house_id}")
        total_charging = sum(plan['planned_charging_kwh'] for plan in charging_plan)
        total_cost = sum(plan['planned_charging_kwh'] * prices[plan['hour']] for plan in charging_plan)
        logger.info(f"Celkem naplánováno: {total_charging:.2f} kWh za {total_cost:.2f} Kč")
        
        # Podrobné logování
        print(f"\n{'='*80}")
        print(f"OPTIMALIZACE NABÍJENÍ LP PRO DŮM {house_id}")
        print(f"{'='*80}")
        print(f"\nPARAMETRY BATERIE:")
        print(f"- Kapacita: {battery_capacity} kWh")
        print(f"- Aktuální stav: {current_level} kWh")
        print(f"- Minimální úroveň: {min_battery_level} kWh ({min_battery_level_pct}%)")
        print(f"- Efektivní minimální úroveň: {effective_min_level} kWh ({effective_min_percent}% kapacity)")
        print(f"- Max nabíjecí výkon: {max_charging_power} kW")
        print(f"- Účinnost nabíjení: {charging_efficiency*100}%")
        
        print(f"\nVÝSLEDNÝ PLÁN NABÍJENÍ:")
        print(f"{'Hodina':<10} {'Cena (Kč/kWh)':<15} {'Nabíjení (kWh)':<15} {'Stav baterie (kWh)':<20}")
        print(f"{'-'*60}")
        
        for h in range(n_hours):
            level = pulp.value(battery_level[h])
            amount = charging_plan[h]['planned_charging_kwh']
            price = prices[h]
            print(f"{h:<10} {price:<15.2f} {amount:<15.2f} {level:<20.2f}")
        
        print(f"\nCELKOVÉ NÁKLADY: {total_cost:.2f} Kč")
        print(f"CELKEM DOBITO: {total_charging:.2f} kWh")
        
        return charging_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI LP OPTIMALIZACI pro dům {house_id}: {str(e)}")
        return fallback_charging_plan(house_id, house_data, solar_production, consumption, prices)

def fallback_charging_plan(house_id, house_data, solar_production, consumption, prices):
    """
    Záložní plán nabíjení, který se použije v případě selhání LP optimalizace.
    Jednodušší heuristický přístup pro zajištění základního nabíjení.
    """
    logger.warning(f"Použití záložního plánu nabíjení pro dům {house_id}")
    
    # Zajištění konzistentní délky polí
    n_hours = min(len(solar_production), len(consumption), len(prices))
    solar_production = solar_production[:n_hours]
    consumption = consumption[:n_hours]
    prices = prices[:n_hours]
    
    # Parametry baterie
    battery_capacity = house_data['battery_capacity']
    min_battery_level_pct = house_data['min_battery_level']
    min_battery_level = battery_capacity * (min_battery_level_pct / 100)
    current_level = house_data['current_battery_level']
    charging_efficiency = house_data['charging_efficiency'] / 100
    max_charging_power = house_data['max_charging_power']
    
    # Simulace stavu baterie bez nabíjení
    simulated_levels = [current_level]
    for h in range(1, n_hours):
        prev_level = simulated_levels[-1]
        net_flow = solar_production[h-1] - consumption[h-1]
        new_level = max(0, min(battery_capacity, prev_level + net_flow))
        simulated_levels.append(new_level)
    
    # Identifikace kritických hodin (pod minimem)
    critical_hours = []
    for h in range(n_hours):
        if simulated_levels[h] < min_battery_level:
            critical_hours.append(h)
    
    # Inicializace plánu nabíjení
    charging_plan = [{'hour': h, 'planned_charging_kwh': 0} for h in range(n_hours)]
    
    # Pokud nejsou kritické hodiny, není potřeba nabíjet
    if not critical_hours:
        return charging_plan
    
    # Seřazení hodin podle ceny
    hour_prices = [(h, prices[h]) for h in range(n_hours)]
    hour_prices.sort(key=lambda x: x[1])  # Seřazení podle ceny
    
    # Aktualizace stavu baterie
    updated_levels = simulated_levels.copy()
    
    # Pro každou kritickou hodinu
    for critical_hour in critical_hours:
        # Kolik energie potřebujeme dodat, aby baterie byla na minimu
        energy_needed = (min_battery_level - updated_levels[critical_hour]) / charging_efficiency
        
        if energy_needed <= 0:
            continue
            
        # Najdi nejlevnější hodiny před kritickou hodinou
        valid_hours = [(h, p) for h, p in hour_prices if h < critical_hour]
        
        # Plánování nabíjení
        for h, _ in valid_hours:
            # Kolik energie můžeme v této hodině dobít
            existing_charge = charging_plan[h]['planned_charging_kwh']
            available = min(max_charging_power - existing_charge, 
                          energy_needed)
            
            if available <= 0:
                continue
                
            # Aktualizuj plán
            charging_plan[h]['planned_charging_kwh'] += available
            energy_gained = available * charging_efficiency
            
            # Aktualizuj stav baterie pro všechny následující hodiny
            for future_h in range(h + 1, n_hours):
                updated_levels[future_h] += energy_gained
            
            energy_needed -= available
            
            if energy_needed <= 0:
                break
    
    return charging_plan

def save_charging_schedule(house_id, charging_plan):
    """
    Uloží plán nabíjení do databáze.
    Nahrazuje stávající plány pro daný dům.
    """
    try:
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()
        
        # Nejprve smažeme existující plány
        cur.execute("""
            DELETE FROM api_chargingschedule
            WHERE house_id = %s
        """, [house_id])
        
        # Uložíme nové plány
        saved_count = 0
        current_time = datetime.now()
        today = current_time.date()
        tomorrow = today + timedelta(days=1)
        
        for plan_item in charging_plan:
            hour = plan_item['hour']
            amount = plan_item['planned_charging_kwh']
            
            if amount <= 0:
                continue
                
            # Určení data podle hodiny
            if hour < 24:
                plan_date = today
            else:
                plan_date = tomorrow
                hour = hour % 24
            
            cur.execute("""
                INSERT INTO api_chargingschedule
                (house_id, date, hour, planned_charging_kwh)
                VALUES (%s, %s, %s, %s)
            """, [
                house_id,
                plan_date,
                hour,
                amount
            ])
            saved_count += 1
        
        conn.commit()
        logger.info(f"ULOŽEN PLÁN NABÍJENÍ: {saved_count} záznamů pro dům {house_id}")
        print(f"Úspěšně uloženo {saved_count} plánů nabíjení do databáze")
        
    except Exception as e:
        logger.error(f"CHYBA PŘI UKLÁDÁNÍ PLÁNU NABÍJENÍ: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def plan_charging_for_house(house_id):
    """
    Kompletní proces plánování nabíjení pro jeden dům.
    Zohledňuje dostupnost dat o cenách elektřiny (k dispozici v 17:00 na další den).
    """
    try:
        print("\n" + "*"*100)
        print(f"ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        print("*"*100)
        
        # 1. Zjistíme aktuální čas a posuneme plánování od následující hodiny
        current_time = datetime.now()
        # Posun na další hodinu
        next_hour = current_time.hour + 1
        current_date = current_time.date()
        tomorrow = current_date + timedelta(days=1)
        
        # Určíme, zda máme k dispozici data o cenách elektřiny na zítřek
        have_tomorrow_prices = current_time.hour >= 17  # Po 17. hodině máme ceny na zítřek
        
        if have_tomorrow_prices:
            print(f"Aktuální čas: {current_time.strftime('%H:%M')} - Máme k dispozici ceny na zítřek")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {tomorrow.strftime('%Y-%m-%d')} 23:59"
        else:
            print(f"Aktuální čas: {current_time.strftime('%H:%M')} - Ceny na zítřek ještě nejsou k dispozici")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {current_date.strftime('%Y-%m-%d')} 23:59"
        
        print(f"Plánovací horizont: {planning_horizon}")
        
        # 2. Získání dat o domu
        print("\nKROK 1: NAČÍTÁNÍ DAT O DOMU")
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} nenalezen")
            print(f"CHYBA: Dům {house_id} nenalezen!")
            return False
            
        print(f"Úspěšně načtena data o domu {house_id}:")
        print(f"- Riziko: {house_data['risk_level']}")
        print(f"- Solární výkon: {house_data['solar_power']} kWp")
        print(f"- Kapacita baterie: {house_data['battery_capacity']} kWh")
        print(f"- Aktuální stav: {house_data['current_battery_level']} kWh")
        print(f"- Min. úroveň: {house_data['min_battery_level']}%")
        print(f"- Max. nabíjecí výkon: {house_data['max_charging_power']} kW")
        print(f"- Účinnost nabíjení: {house_data['charging_efficiency']}%")
        
        # 3. Získání cen elektřiny
        print("\nKROK 2: ZÍSKÁNÍ CEN ELEKTŘINY")
        prices = get_price_data(
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        if not prices:
            print("CHYBA: Žádná data o cenách elektřiny nebyla nalezena!")
            return False
            
        print(f"Úspěšně načteny ceny elektřiny pro {len(prices)} hodin")
            
        # Ukázka cen
        print("\nUkázka cen elektřiny (10 nejlevnějších hodin):")
        sorted_prices = [(h, p) for h, p in enumerate(prices)]
        sorted_prices.sort(key=lambda x: x[1])
        for h, price in sorted_prices[:10]:
            print(f"Hodina {h}: {price:.3f} Kč/kWh")
        
        # 4. Získání predikce solární výroby
        print("\nKROK 3: ZÍSKÁNÍ PREDIKCE SOLÁRNÍ VÝROBY")
        solar_production = get_solar_prediction(
            house_power=house_data['solar_power'],
            charging_efficiency=house_data['charging_efficiency'],
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        print(f"Úspěšně načtena predikce solární výroby pro {len(solar_production)} hodin")
        
        # 5. Získání predikce spotřeby
        print("\nKROK 4: ZÍSKÁNÍ PREDIKCE SPOTŘEBY")
        consumption = get_consumption_prediction(
            house_id, 
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        print(f"Úspěšně načtena predikce spotřeby pro {len(consumption)} hodin")
        
        # 6. Optimalizace plánu nabíjení pomocí lineárního programování
        print("\nKROK 5: OPTIMALIZACE PLÁNU NABÍJENÍ")
        charging_plan = optimize_charging_lp(
            house_id,
            house_data,
            solar_production,
            consumption,
            prices
        )
        
        # 7. Uložení plánu do databáze
        print("\nKROK 6: ULOŽENÍ PLÁNU DO DATABÁZE")
        save_charging_schedule(house_id, charging_plan)
        
        print("\n" + "*"*100)
        print(f"KONEC PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        print("*"*100)
        
        return True
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}: {str(e)}")
        print(f"\nCHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        logger.info("ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ")
        
        # Získání seznamu aktivních domů
        active_houses = get_active_houses()
        logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Zpracovávám {len(active_houses)} aktivních domů")
        
        print(f"Nalezeno {len(active_houses)} aktivních domů: {active_houses}")
        
        # Plánování pro každý dům
        for house_id in active_houses:
            result = plan_charging_for_house(house_id)
            status = "úspěšně" if result else "neúspěšně"
            logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} zpracován {status}")
        
        logger.info("KONEC PLÁNOVÁNÍ NABÍJENÍ")
        
    except Exception as e:
        logger.error(f"KRITICKÁ CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ: {str(e)}")
        print(f"KRITICKÁ CHYBA: {str(e)}")