import psycopg2
import logging
from datetime import datetime, timedelta
from tabulate import tabulate

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
    NOVÝ algoritmus pro optimalizaci nabíjení, který prioritizuje nejlevnější hodiny
    a zajišťuje minimální úrovně nabití v závislosti na úrovni rizika a ceně.
    
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
        
        # Výpočet průměrné ceny pro určení kategorií cen
        avg_price = sum(hour['price'] for hour in price_data) / len(price_data)
        low_price_threshold = avg_price * 0.7  # 70% průměrné ceny
        very_low_price_threshold = avg_price * 0.4  # 40% průměrné ceny
        
        # Seřadíme hodiny podle ceny (od nejlevnější po nejdražší)
        sorted_price_data = sorted(price_data, key=lambda x: x['price'])
        
        # Kategorizace cen
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
        
        # Inicializace plánu nabíjení - žádné nabíjení
        charging_plan = [0] * n_hours
        
        # Simulace stavu baterie bez nabíjení
        def simulate_battery_levels(charging_plan):
            levels = []
            current_level = current_battery_level
            
            for i in range(n_hours):
                # Solární výroba v této hodině
                solar = solar_data[i]['solar_kwh'] if i < len(solar_data) else 0
                
                # Spotřeba v této hodině
                consumption = consumption_data[i]['consumption_kwh'] if i < len(consumption_data) else 0
                
                # Nabíjení z plánu (s aplikací účinnosti)
                charging = charging_plan[i] * charging_efficiency if i < len(charging_plan) else 0
                
                # Čistý tok energie
                net_flow = solar - consumption + charging
                
                # Nový stav baterie
                current_level = min(battery_capacity, max(0, current_level + net_flow))
                
                levels.append({
                    'hour': price_data[i]['hour'],
                    'date': price_data[i]['date'],
                    'level': current_level,
                    'net_flow': net_flow,
                    'solar': solar,
                    'consumption': consumption,
                    'charging': charging_plan[i],
                    'min_level': min_battery_level,  # absolutní minimum
                    'target_level': price_data[i]['target_level']  # cílová úroveň dle kategorie
                })
                
            return levels
        
        # Krok 1: Optimalizace od nejlevnější hodiny
        for cheap_hour in sorted_price_data:
            index = cheap_hour['index']
            
            # Simulujeme stav baterie s aktuálním plánem
            battery_levels = simulate_battery_levels(charging_plan)
            
            # Zjistíme stav baterie v této hodině po současném plánu
            current_level = battery_levels[index]['level']
            
            # Zjistíme cílovou úroveň pro tuto hodinu podle kategorie ceny
            target_level = cheap_hour['target_level']
            
            # Pokud jsme pod cílovou úrovní, naplánujeme nabíjení
            if current_level < target_level:
                # Spočítáme, kolik potřebujeme dobít
                energy_needed = (target_level - current_level) / charging_efficiency
                
                # Omezíme množství na maximální nabíjecí výkon
                amount_to_charge = min(energy_needed, max_charging_power)
                
                # Aktualizujeme plán
                charging_plan[index] = amount_to_charge
                
                logger.info(f"Plánuji nabíjení {amount_to_charge:.2f} kWh v hodině {cheap_hour['hour']}:00 (cena: {cheap_hour['price']:.2f} Kč/kWh)")
            
        # Krok 2: Kontrola, zda nemáme někde hodiny pod absolutním minimem
        battery_levels = simulate_battery_levels(charging_plan)
        critical_hours = [h for h in battery_levels if h['level'] < min_battery_level]
        
        if critical_hours:
            logger.warning(f"Nalezeno {len(critical_hours)} kritických hodin pod absolutním minimem")
            
            # Pro každou kritickou hodinu
            for critical_hour in critical_hours:
                critical_index = battery_levels.index(critical_hour)
                
                # Najdeme předchozí hodiny, seřazené podle ceny
                previous_hours = [(i, price_data[i]) for i in range(critical_index)]
                previous_hours.sort(key=lambda x: x[1]['price'])
                
                if not previous_hours:
                    logger.error(f"Kritická hodina {critical_hour['hour']}:00 nemá žádné předchozí hodiny pro nabíjení")
                    continue
                
                # Kolik potřebujeme dodat energie
                deficit = min_battery_level - critical_hour['level']
                energy_needed = deficit / charging_efficiency
                
                logger.info(f"Kritická hodina {critical_hour['hour']}:00 - deficit {deficit:.2f} kWh, potřeba dobít {energy_needed:.2f} kWh")
                
                # Rozdělíme nabíjení do nejlevnějších předchozích hodin
                for idx, _ in previous_hours:
                    if energy_needed <= 0:
                        break
                        
                    # Kolik můžeme dobít v této hodině
                    available_capacity = max_charging_power - charging_plan[idx]
                    amount_to_add = min(available_capacity, energy_needed)
                    
                    if amount_to_add > 0:
                        charging_plan[idx] += amount_to_add
                        energy_needed -= amount_to_add
                        
                        logger.info(f"Přidáno {amount_to_add:.2f} kWh v hodině {price_data[idx]['hour']}:00 pro řešení kritické hodiny")
                
                # Přepočítáme stav baterie
                battery_levels = simulate_battery_levels(charging_plan)
        
        # Převedeme plán do standardního formátu
        final_plan = []
        for i, amount in enumerate(charging_plan):
            if i >= len(price_data):
                break
                
            hour_data = price_data[i]
            battery_level = battery_levels[i]['level']
            
            final_plan.append({
                'hour': hour_data['hour'],
                'date': hour_data['date'],
                'planned_charging_kwh': amount,
                'target_level': hour_data['target_level'],
                'battery_level': battery_level,
                'price': hour_data['price']
            })
        
        # Příprava tabulkového výpisu
        table_data = []
        headers = [
            "Datum", "Hodina", "Cena\n(Kč/kWh)", "Spotřeba\n(kWh)", 
            "Solár\n(kWh)", "Nabíjení\n(kWh)", "Stav baterie\n(kWh)", 
            "Stav baterie\n(%)", "Kategorie\nceny"
        ]

        for i, plan in enumerate(final_plan):
            # Doplnění spotřeby a solární výroby z dostupných dat
            solar = solar_data[i]['solar_kwh'] if i < len(solar_data) else 0
            consumption = consumption_data[i]['consumption_kwh'] if i < len(consumption_data) else 0
            
            battery_percentage = (plan['battery_level'] / battery_capacity) * 100
            
            # Určení kategorie ceny
            if plan['price'] <= very_low_price_threshold:
                price_category = 'Velmi nízká'
            elif plan['price'] <= low_price_threshold:
                price_category = 'Nízká'
            else:
                price_category = 'Standardní'
            
            table_data.append([
                plan['date'].strftime('%Y-%m-%d'),
                f"{plan['hour']:02d}:00",
                f"{plan['price']:.3f}",
                f"{consumption:.3f}",
                f"{solar:.3f}",
                f"{plan['planned_charging_kwh']:.3f}",
                f"{plan['battery_level']:.3f}",
                f"{battery_percentage:.1f}",
                price_category
            ])
        
        # Vytvoření tabulky
        table_str = tabulate(
            table_data, 
            headers=headers, 
            tablefmt='pipe',  # Markdown-like formátování
            numalign='right'
        )
        
        # Výpis tabulky do logu
        print("\n" + "=" * 120)
        print(f"PLÁN NABÍJENÍ PRO DŮM {house_id}")
        print("=" * 120)
        print(table_str)
        print("\n" + "=" * 120)
        
        logger.info(f"\nPLÁN NABÍJENÍ PRO DŮM {house_id}:\n{table_str}")
        
        # Výpočet celkových nákladů
        total_cost = sum(plan['planned_charging_kwh'] * plan['price'] for plan in final_plan)
        total_energy = sum(plan['planned_charging_kwh'] for plan in final_plan)
        
        logger.info(f"OPTIMALIZACE DOKONČENA: Naplánováno {total_energy:.2f} kWh za {total_cost:.2f} Kč")
        
        return final_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI OPTIMALIZACI NABÍJENÍ: {str(e)}")
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