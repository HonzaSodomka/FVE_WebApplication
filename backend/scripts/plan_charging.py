import psycopg2
import logging
from datetime import datetime, timedelta

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
        Seznam objektů s informacemi o cenách pro každou hodinu v plánovacím horizontu
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
        
        prices = []
        rows = cur.fetchall()
        
        for date, hour, price in rows:
            prices.append({
                'date': date,
                'hour': hour,
                'price': price / 1000,  # Převod z Kč/MWh na Kč/kWh
                'index': len(prices)     # Index v plánovacím horizontu
            })
            
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

def get_solar_prediction(house_power, current_hour, have_tomorrow_prices=False):
    """
    Získá předpověď solární výroby a upraví ji podle výkonu domu
    
    Args:
        house_power: Výkon solárních panelů v kWp
        current_hour: Aktuální hodina dne (0-23)
        have_tomorrow_prices: Zda jsou k dispozici ceny na zítřek
        
    Returns:
        Seznam objektů s predikcí solární výroby pro každou hodinu v plánovacím horizontu
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
        
        solar_data = []

        # Načteme všechna data solární produkce pro dnešek
        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today])
        
        rows = cur.fetchall()
        logger.info(f"Načteno {len(rows)} záznamů predikce solární výroby")
        
        # Přepočítací faktory
        power_ratio = house_power / 20  # Základní predikce je na 20kWp
        
        # Vytvoříme slovník s produkcí dle hodin pro dnešek
        hour_production_today = {}
        
        for timestamp, wh in rows:
            hour = timestamp.hour
            
            # Poslední záznam, který není v celé hodině, přiřadíme k další hodině
            if timestamp.minute > 0 and hour < 23:
                next_hour = hour + 1
                if next_hour not in hour_production_today:
                    hour_production_today[next_hour] = wh
            else:
                if hour not in hour_production_today:
                    hour_production_today[hour] = wh
        
        # Vytvoříme pole solární produkce pro všechny hodiny v plánovacím horizontu
        if have_tomorrow_prices:
            # Máme data na zítřek, plánujeme od current_hour do 23 hodin následujícího dne
            n_hours = (24 - current_hour) + 24
        else:
            # Nemáme data na zítřek, plánujeme od current_hour do 23 hodin dnes
            n_hours = 24 - current_hour
            
        # Pro indexování v plánovacím horizontu
        index = 0
            
        # Plnění dat pro dnešek
        for hour in range(current_hour, 24):
            solar_kwh = hour_production_today.get(hour, 0) * power_ratio / 1000
            solar_data.append({
                'date': today,
                'hour': hour,
                'solar_kwh': solar_kwh,
                'index': index
            })
            index += 1
            
        # Plnění dat pro zítřek (pokud máme ceny)
        if have_tomorrow_prices:
            # Pokud máme data na zítřek, musíme je také načíst
            cur.execute("""
                SELECT timestamp, watt_hours_period
                FROM api_solardata 
                WHERE DATE(timestamp) = %s
                ORDER BY timestamp
            """, [tomorrow])
            
            tomorrow_rows = cur.fetchall()
            hour_production_tomorrow = {}
            
            for timestamp, wh in tomorrow_rows:
                hour = timestamp.hour
                
                if timestamp.minute > 0 and hour < 23:
                    next_hour = hour + 1
                    if next_hour not in hour_production_tomorrow:
                        hour_production_tomorrow[next_hour] = wh
                else:
                    if hour not in hour_production_tomorrow:
                        hour_production_tomorrow[hour] = wh
                        
            # Plnění dat pro zítřek
            for hour in range(24):
                solar_kwh = hour_production_tomorrow.get(hour, 0) * power_ratio / 1000
                solar_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'solar_kwh': solar_kwh,
                    'index': index
                })
                index += 1
        
        logger.info(f"NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Vytvořena předpověď pro {len(solar_data)} hodin")
        
        return solar_data
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: {str(e)}")
        # V případě chyby, vracíme prázdné pole
        return []
        
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
        Seznam objektů s predikcí spotřeby pro každou hodinu v plánovacím horizontu
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
        consumption_data = []
        index = 0
        
        # Pro dnešek od aktuální hodiny
        today_type = 'weekend' if is_today_weekend else 'weekday'
        for hour in range(current_hour, 24):
            consumption_wh = averages[today_type].get(hour, 0)
            consumption_data.append({
                'date': today,
                'hour': hour,
                'consumption_kwh': consumption_wh / 1000,  # Převod na kWh
                'index': index
            })
            index += 1
            
        # Pro zítřek všechny hodiny, jen pokud máme ceny na zítřek
        if have_tomorrow_prices:
            tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
            for hour in range(24):
                consumption_wh = averages[tomorrow_type].get(hour, 0)
                consumption_data.append({
                    'date': tomorrow,
                    'hour': hour,
                    'consumption_kwh': consumption_wh / 1000,  # Převod na kWh
                    'index': index
                })
                index += 1
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return consumption_data
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        # V případě chyby, vracíme prázdné pole
        return []
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def optimize_charging_plan(house_id, house_data, solar_data, consumption_data, price_data):
    """
    Optimalizace nabíjení podle cenově-efektivního přístupu.
    
    Pro každou hodinu od nejlevnější:
    1. Definujeme její cílovou úroveň (target) pro konec dne
    2. Plánujeme nabíjení tak, aby baterie na konci dne dosáhla tohoto cíle
    3. Zohledňujeme kapacitu baterie, maximální výkon a solární výrobu
    
    Args:
        house_id: ID domu
        house_data: Objekt s parametry domu
        solar_data: Pole s predikcí solární výroby pro každou hodinu
        consumption_data: Pole s predikcí spotřeby pro každou hodinu
        price_data: Pole s cenami elektřiny pro každou hodinu
    
    Returns:
        Seznam s plánem nabíjení pro každou hodinu
    """
    try:
        logger.info(f"ZAČÁTEK OPTIMALIZACE NABÍJENÍ PRO DŮM {house_id}")
        
        # Získáme základní parametry domu
        battery_capacity = house_data['battery_capacity']
        current_battery_level = house_data['current_battery_level']
        min_battery_level_pct = house_data['min_battery_level']
        min_battery_level = battery_capacity * (min_battery_level_pct / 100)  # Převod % na kWh
        max_charging_power = house_data['max_charging_power']
        charging_efficiency = house_data['charging_efficiency'] / 100
        risk_level = house_data['risk_level']
        
        # Definice úrovní podle risk_level
        risk_level_settings = {
            'LOW': {
                'standard_min': 50,  # Standardní minimum 50%
                'flexible_min': 30,  # Flexibilní minimum 30%
                'target_reserve': 70  # Cílová rezerva 70%
            },
            'MEDIUM': {
                'standard_min': 25,
                'flexible_min': 15,
                'target_reserve': 35
            },
            'HIGH': {
                'standard_min': 10,
                'flexible_min': 5,
                'target_reserve': 20
            }
        }
        
        # Nastavení podle zvoleného risk_level
        settings = risk_level_settings.get(
            risk_level, 
            risk_level_settings['MEDIUM']  # Výchozí hodnoty
        )
        
        standard_min_level = battery_capacity * (settings['standard_min'] / 100)
        flexible_min_level = battery_capacity * (settings['flexible_min'] / 100)
        target_level = battery_capacity * (settings['target_reserve'] / 100)
        
        # Počet hodin v plánovacím horizontu
        n_hours = len(price_data)
        
        # Ujistíme se, že máme konzistentní délku všech dat
        if len(solar_data) < n_hours:
            logger.warning(f"Solární data mají méně záznamů ({len(solar_data)}) než horizont plánování ({n_hours})")
            # Doplníme solární data nulami
            for i in range(len(solar_data), n_hours):
                solar_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'solar_kwh': 0,
                    'index': i
                })
                
        if len(consumption_data) < n_hours:
            logger.warning(f"Data spotřeby mají méně záznamů ({len(consumption_data)}) než horizont plánování ({n_hours})")
            # Doplníme data spotřeby průměrnými hodnotami
            avg_consumption = sum(item['consumption_kwh'] for item in consumption_data) / len(consumption_data) if consumption_data else 0.2
            for i in range(len(consumption_data), n_hours):
                consumption_data.append({
                    'date': price_data[i]['date'],
                    'hour': price_data[i]['hour'],
                    'consumption_kwh': avg_consumption,
                    'index': i
                })
        
        # Výpočet průměrné ceny pro určení kategorií cen
        avg_price = sum(hour['price'] for hour in price_data) / len(price_data)
        low_price_threshold = avg_price * 0.7  # 70% průměrné ceny
        very_low_price_threshold = avg_price * 0.4  # 40% průměrné ceny
        
        # Určení cílové úrovně pro každou hodinu podle kategorie ceny
        for hour in price_data:
            if hour['price'] <= very_low_price_threshold:
                hour['price_category'] = 'very_low'
                hour['target_level'] = target_level
            elif hour['price'] <= low_price_threshold:
                hour['price_category'] = 'low'
                hour['target_level'] = standard_min_level
            else:
                hour['price_category'] = 'standard'
                hour['target_level'] = flexible_min_level
        
        # Výpis kategorií cen
        logger.info(f"Průměrná cena: {avg_price:.2f} Kč/kWh")
        logger.info(f"Limit nízkých cen: {low_price_threshold:.2f} Kč/kWh")
        logger.info(f"Limit velmi nízkých cen: {very_low_price_threshold:.2f} Kč/kWh")
        
        # Seřadíme hodiny podle ceny (od nejlevnější po nejdražší)
        sorted_price_indices = sorted(range(n_hours), key=lambda i: price_data[i]['price'])
        
        # Funkce pro simulaci stavu baterie na základě plánu nabíjení
        def simulate_battery_levels(charging_plan):
            levels = []
            current_level = current_battery_level
            
            for i in range(n_hours):
                # Solární výroba v této hodině
                solar = solar_data[i]['solar_kwh'] if i < len(solar_data) else 0
                
                # Spotřeba v této hodině
                consumption = consumption_data[i]['consumption_kwh'] if i < len(consumption_data) else 0
                
                # Nabíjení z plánu (ze sítě)
                charging_grid = charging_plan[i] if i < len(charging_plan) else 0
                
                # Aplikujeme účinnost na veškeré nabíjení (jak ze sítě, tak ze solárů)
                effective_solar = solar * charging_efficiency
                effective_grid_charging = charging_grid * charging_efficiency
                
                # Čistý tok energie
                net_flow = effective_solar - consumption + effective_grid_charging
                
                # Nový stav baterie
                current_level = min(battery_capacity, max(0, current_level + net_flow))
                
                levels.append({
                    'hour': price_data[i]['hour'],
                    'date': price_data[i]['date'],
                    'level': current_level,
                    'net_flow': net_flow,
                    'solar': solar,
                    'effective_solar': effective_solar,
                    'consumption': consumption,
                    'charging_grid': charging_grid,
                    'effective_grid_charging': effective_grid_charging,
                    'price': price_data[i]['price'],
                    'price_category': price_data[i]['price_category'],
                    'target_level': price_data[i]['target_level'],
                    'index': i
                })
                
            return levels
        
        # Inicializace plánu nabíjení - žádné nabíjení
        charging_plan = [0] * n_hours
        
        # Počáteční simulace pro zjištění stavu bez nabíjení
        initial_levels = simulate_battery_levels(charging_plan)
        
        # Výpis počátečního stavu
        logger.info("Počáteční stav baterie bez nabíjení:")
        for level in initial_levels:
            logger.info(f"Hodina {level['hour']}:00 - {level['level']:.2f} kWh ({level['level']/battery_capacity*100:.1f}%)")
        
        # Pro každou hodinu v pořadí od nejlevnější
        for hour_idx in sorted_price_indices:
            current_hour = price_data[hour_idx]
            hour_target = current_hour['target_level']
            
            logger.info(f"Zpracovávám hodinu {current_hour['hour']}:00 s cenou {current_hour['price']:.2f} Kč/kWh (target: {hour_target/battery_capacity*100:.1f}%)")
            
            # 1. Zjistíme, jaký bude stav baterie na konci období s aktuálním plánem
            current_levels = simulate_battery_levels(charging_plan)
            end_level = current_levels[-1]['level']
            
            # 2. Plánování nabíjení pro aktuální hodinu
            if end_level < hour_target:
                # Získáme informace o solární výrobě v této hodině
                solar_hour = next((s for s in solar_data if s['hour'] == current_hour['hour'] and s['date'] == current_hour['date']), None)
                solar_production = solar_hour['solar_kwh'] if solar_hour else 0
                
                # Maximální nabíjecí výkon baterie je omezení pro celkový přísun energie (síť + solar)
                # Musíme odečíst solární výrobu, abychom dostali kolik můžeme ještě nabíjet ze sítě
                available_charging_power = max(0, max_charging_power - solar_production)
                max_hour_charging = available_charging_power  # kW na hodinu = kWh
                
                logger.info(f"Plánuji nabíjení pro hodinu {current_hour['hour']}:00")
                
                # Simulujeme plán s maximálním nabíjením v této hodině
                test_charging_plan = charging_plan.copy()
                test_charging_plan[hour_idx] = max_hour_charging
                test_levels = simulate_battery_levels(test_charging_plan)
                
                # Kontrolujeme:
                # 1. Přesah 100% kapacity (v jakékoliv budoucí hodině)
                # 2. Přesah cíle na konci plánovacího období
                
                # Hledáme nejvyšší přesah kapacity baterie
                max_level = 0
                max_level_hour = None
                capacity_excess = 0
                
                for i, level in enumerate(test_levels[hour_idx:], hour_idx):
                    if level['level'] > max_level:
                        max_level = level['level']
                        max_level_hour = level['hour']
                        
                if max_level > battery_capacity * 0.999:
                    capacity_excess = max_level - battery_capacity
                    logger.info(f"V hodině {max_level_hour}:00 by baterie překročila kapacitu o {capacity_excess:.2f} kWh")
                
                # Zjišťujeme přesah cíle na konci období
                end_test_level = test_levels[-1]['level']
                target_excess = 0
                
                if end_test_level > hour_target:
                    target_excess = end_test_level - hour_target
                    logger.info(f"Konečný stav baterie by překročil cíl {hour_target:.2f} kWh o {target_excess:.2f} kWh")
                
                # Vypočítáme, kolik energie musíme odebrat (větší z obou přesahů)
                energy_excess = max(capacity_excess, target_excess)
                
                # Určíme finální nabíjení 
                planned_charging = max_hour_charging
                
                if energy_excess > 0:
                    # Musíme snížit nabíjení o přesah
                    excess_charging = energy_excess / charging_efficiency
                    planned_charging = max(0, max_hour_charging - excess_charging)
                    logger.info(f"Snižuji nabíjení o {excess_charging:.2f} kWh na {planned_charging:.2f} kWh")
                
                # Nastavíme plán nabíjení
                charging_plan[hour_idx] = planned_charging
                
                # Aktualizujeme simulaci a zkontrolujeme výsledek
                current_levels = simulate_battery_levels(charging_plan)
                end_level = current_levels[-1]['level']
                
                target_reached = end_level >= hour_target
                
                logger.info(f"Finální plán pro hodinu {current_hour['hour']}:00:")
                logger.info(f" - Naplánované nabíjení ze sítě: {planned_charging:.2f} kWh")
                logger.info(f" - Solární výroba v této hodině: {solar_production:.2f} kWh")
                logger.info(f" - Celkový přísun energie: {(planned_charging + solar_production):.2f} kWh")
                logger.info(f" - Max. nabíjecí výkon baterie: {max_charging_power:.2f} kW")
                logger.info(f" - Dostupný výkon pro nabíjení ze sítě: {available_charging_power:.2f} kW")
                logger.info(f" - Konečný stav baterie: {end_level:.2f} kWh ({end_level/battery_capacity*100:.1f}%)")
                logger.info(f" - Cíl splněn: {'ANO' if target_reached else 'NE'}")
            
            else:
                logger.info(f"Konečný stav baterie {end_level:.2f} kWh již splňuje cíl {hour_target:.2f} kWh, není potřeba nabíjet")
        
        # Finální stav baterie po všech úpravách
        final_levels = simulate_battery_levels(charging_plan)
        
        # Vytvoření finálního plánu
        final_plan = []
        for i in range(n_hours):
            level = final_levels[i]
            plan = {
                'hour': level['hour'],
                'date': level['date'],
                'planned_charging_kwh': charging_plan[i],
                'battery_level': level['level'],
                'battery_percent': level['level'] / battery_capacity * 100,
                'price': level['price'],
                'price_category': level['price_category'],
                'target_level': level['target_level'],
                'target_percent': level['target_level'] / battery_capacity * 100,
                'solar_production': level['solar'],
                'consumption': level['consumption']
            }
            final_plan.append(plan)
        
        # Logování výsledků
        logger.info("Finální plán nabíjení:")
        for plan in final_plan:
            if plan['planned_charging_kwh'] > 0:
                logger.info(f"Hodina {plan['hour']}:00 - nabíjení {plan['planned_charging_kwh']:.2f} kWh (cena: {plan['price']:.2f} Kč/kWh)")
        
        # Výpočet celkových nákladů
        total_energy = sum(plan['planned_charging_kwh'] for plan in final_plan)
        total_cost = sum(plan['planned_charging_kwh'] * plan['price'] for plan in final_plan)
        
        logger.info(f"Celkové nabíjení: {total_energy:.2f} kWh")
        logger.info(f"Celkové náklady: {total_cost:.2f} Kč")
        
        # Výpis stavu baterie na konci plánovacího horizontu
        if final_plan:
            last_plan = final_plan[-1]
            logger.info(f"Konečný stav baterie: {last_plan['battery_level']:.2f} kWh ({last_plan['battery_percent']:.1f}%)")
        
        # Výpis finálního plánu v přehledné tabulce
        logger.info("=" * 120)
        logger.info(f"PLÁN NABÍJENÍ PRO DŮM {house_id}")
        logger.info("=" * 120)
        logger.info(f"| {'Datum':<10} | {'Hodina':<8} | {'Cena':>10} | {'Spotřeba':>10} | {'Solár':>7} | {'Nabíjení':>10} | {'Stav baterie':>15} | {'Stav baterie':>15} | {'Kategorie':<10} |")
        logger.info(f"| {'':<10} | {'':<8} | {'(Kč/kWh)':>10} | {'(kWh)':>10} | {'(kWh)':>7} | {'(kWh)':>10} | {'(kWh)':>15} | {'(%)':>15} | {'ceny':<10} |")
        logger.info(f"|:{'-'*10}|:{'-'*8}|{'-'*10}:|{'-'*10}:|{'-'*7}:|{'-'*10}:|{'-'*15}:|{'-'*15}:|:{'-'*10}|")
        
        for plan in final_plan:
            date_str = plan['date'].strftime('%Y-%m-%d')
            hour_str = f"{plan['hour']}:00"
            price_str = f"{plan['price']:.3f}"
            consumption_str = f"{plan['consumption']:.3f}"
            solar_str = f"{plan['solar_production']:.3f}"
            charging_str = f"{plan['planned_charging_kwh']:.3f}"
            level_str = f"{plan['battery_level']:.3f}"
            percent_str = f"{plan['battery_percent']:.1f}"
            
            category_map = {
                'very_low': 'Velmi nízká',
                'low': 'Nízká',
                'standard': 'Standardní'
            }
            category_str = category_map.get(plan['price_category'], plan['price_category'])
            
            logger.info(f"| {date_str:<10} | {hour_str:<8} | {price_str:>10} | {consumption_str:>10} | {solar_str:>7} | {charging_str:>10} | {level_str:>15} | {percent_str:>15} | {category_str:<10} |")
        
        logger.info("=" * 120)
        
        return final_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI OPTIMALIZACI NABÍJENÍ: {str(e)}", exc_info=True)
        # V případě chyby vracíme prázdný plán
        return []
    
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
        
        for plan_item in charging_plan:
            hour = plan_item['hour']
            amount = plan_item['planned_charging_kwh']
            date = plan_item['date']
            
            if amount <= 0:
                continue
            
            cur.execute("""
                INSERT INTO api_chargingschedule
                (house_id, date, hour, planned_charging_kwh)
                VALUES (%s, %s, %s, %s)
            """, [
                house_id,
                date,
                hour,
                amount
            ])
            saved_count += 1
        
        conn.commit()
        logger.info(f"ULOŽEN PLÁN NABÍJENÍ: {saved_count} záznamů pro dům {house_id}")
        
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
        logger.info(f"ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        
        # 1. Zjistíme aktuální čas a posuneme plánování od následující hodiny
        current_time = datetime.now()
        # Posun na další hodinu - skripty se spouští v xx:59, takže plánujeme od další hodiny
        next_hour = current_time.hour + 1
        current_date = current_time.date()
        tomorrow = current_date + timedelta(days=1)
        
        # Určíme, zda máme k dispozici data o cenách elektřiny na zítřek
        # Pokud je aktuální hodina >= 17, máme data na zítřek
        have_tomorrow_prices = current_time.hour >= 17
        
        if have_tomorrow_prices:
            logger.info(f"Aktuální čas: {current_time.strftime('%H:%M')} - Máme k dispozici ceny na zítřek")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {tomorrow.strftime('%Y-%m-%d')} 23:59"
        else:
            logger.info(f"Aktuální čas: {current_time.strftime('%H:%M')} - Ceny na zítřek ještě nejsou k dispozici")
            planning_horizon = f"od {current_date.strftime('%Y-%m-%d')} {next_hour}:00 do {current_date.strftime('%Y-%m-%d')} 23:59"
        
        logger.info(f"Plánovací horizont: {planning_horizon}")
        
        # 2. Získání dat o domu
        house_data = get_house_data(house_id)
        if not house_data:
            logger.error(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} nenalezen")
            return False
        
        # 3. Získání cen elektřiny
        price_data = get_price_data(
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        if not price_data:
            logger.error("PLÁNOVÁNÍ NABÍJENÍ: Žádná data o cenách elektřiny nebyla nalezena")
            return False
            
        # 4. Získání predikce solární výroby
        solar_data = get_solar_prediction(
            house_power=house_data['solar_power'],
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        # 5. Získání predikce spotřeby
        consumption_data = get_consumption_prediction(
            house_id, 
            current_hour=next_hour,
            have_tomorrow_prices=have_tomorrow_prices
        )
        
        # 6. Optimalizace plánu nabíjení s novým algoritmen
        charging_plan = optimize_charging_plan(
            house_id,
            house_data,
            solar_data,
            consumption_data,
            price_data
        )
        
        # 7. Uložení plánu do databáze
        save_charging_schedule(house_id, charging_plan)
        
        logger.info(f"KONEC PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}: {str(e)}")
        return False
    
if __name__ == "__main__":
    try:
        logger.info("================================")
        logger.info("ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ")
        logger.info("================================")
        
        # Získání seznamu aktivních domů
        active_houses = get_active_houses()
        logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Zpracovávám {len(active_houses)} aktivních domů")
        
        # Plánování pro každý dům
        for house_id in active_houses:
            logger.info(f"------------------------------------")
            logger.info(f"ZAHAJUJI PLÁNOVÁNÍ PRO DŮM {house_id}")
            logger.info(f"------------------------------------")
            
            result = plan_charging_for_house(house_id)
            status = "úspěšně" if result else "neúspěšně"
            logger.info(f"PLÁNOVÁNÍ NABÍJENÍ: Dům {house_id} zpracován {status}")
            logger.info(f"------------------------------------")
        
        logger.info("================================")
        logger.info("KONEC PLÁNOVÁNÍ NABÍJENÍ")
        logger.info("================================")
        
    except Exception as e:
        logger.error(f"KRITICKÁ CHYBA PŘI PLÁNOVÁNÍ NABÍJENÍ: {str(e)}")
        logger.error(f"STACKTRACE: ", exc_info=True)