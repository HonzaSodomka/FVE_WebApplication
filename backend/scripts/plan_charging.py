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

def get_price_data():
    """Získá data o cenách elektřiny pro aktuální a příští den"""
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
        current_hour = current_time.hour

        cur.execute("""
            SELECT date, hour, price_czk 
            FROM api_pricedata 
            WHERE (date = %s AND hour >= %s) OR date = %s
            ORDER BY date, hour
        """, [today, current_hour, tomorrow])
        
        prices = {}
        rows = cur.fetchall()
        
        for date, hour, price in rows:
            date_str = date.strftime('%Y-%m-%d')
            if date_str not in prices:
                prices[date_str] = {}
            prices[date_str][hour] = price / 1000  # Převod z Kč/MWh na Kč/kWh
        
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

def get_solar_prediction(house_power, charging_efficiency):
    """Získá předpověď solární výroby a upraví ji podle výkonu domu a účinnosti nabíjení"""
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
        current_hour = current_time.hour

        cur.execute("""
            SELECT timestamp, watt_hours_period
            FROM api_solardata 
            WHERE (DATE(timestamp) = %s AND EXTRACT(HOUR FROM timestamp) >= %s) 
               OR DATE(timestamp) = %s
            ORDER BY timestamp
        """, [today, current_hour, tomorrow])
        
        production = {}
        rows = cur.fetchall()
        
        power_ratio = house_power / 20
        efficiency_multiplier = charging_efficiency / 100
        
        # První zpracování pro nalezení prvního nenulového záznamu pro každý den
        first_nonzero = {}
        for timestamp, wh in rows:
            date_str = timestamp.strftime('%Y-%m-%d')
            hour = timestamp.hour
            
            if wh > 0:  # Pokud najdeme nenulovou hodnotu
                if date_str not in first_nonzero:  # a ještě nemáme pro tento den
                    first_nonzero[date_str] = hour  # uložíme hodinu
        
        # Druhé zpracování pro skutečné uložení dat
        for timestamp, wh in rows:
            date_str = timestamp.strftime('%Y-%m-%d')
            minutes = timestamp.minute
            hour = timestamp.hour
            
            # Přeskočíme nulové hodnoty před prvním nenulovým záznamem dne
            if hour < first_nonzero.get(date_str, 0) and wh == 0:
                continue
                
            if date_str not in production:
                production[date_str] = {}
            
            # Pokud nejsme na začátku hodiny, posuneme záznam do další hodiny
            if minutes > 0:
                hour = (hour + 1) % 24
                # Pokud přecházíme přes půlnoc, změníme datum
                if hour == 0:
                    date = timestamp.date() + timedelta(days=1)
                    date_str = date.strftime('%Y-%m-%d')
                    if date_str not in production:
                        production[date_str] = {}
            
            # Přepočet na instalovaný výkon a aplikace účinnosti nabíjení
            adjusted_wh = wh * power_ratio * efficiency_multiplier
            production[date_str][hour] = adjusted_wh
        
        logger.info(f"NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Načteno {len(rows)} záznamů pro {house_power}kWp")
        
        if not rows:
            logger.warning("NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: Žádné záznamy nenalezeny")
        
        return production
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ SOLÁRNÍ PREDIKCE: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def get_consumption_prediction(house_id):
    """Získá předpověď spotřeby domu na základě historických dat"""
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
        current_hour = current_time.hour
        
        # Zjistíme typ dnů (víkend/všední)
        is_today_weekend = today.weekday() >= 5
        is_tomorrow_weekend = tomorrow.weekday() >= 5
        
        # Načteme historická data za posledních 30 dní
        start_date = today - timedelta(days=30)
        
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
        
        # Vytvoříme predikci jen pro požadované hodiny
        prediction = {
            today.strftime('%Y-%m-%d'): {},
            tomorrow.strftime('%Y-%m-%d'): {}
        }
        
        # Pro dnešek od aktuální hodiny
        today_type = 'weekend' if is_today_weekend else 'weekday'
        for hour in range(current_hour, 24):
            consumption = averages[today_type].get(hour, 0)
            prediction[today.strftime('%Y-%m-%d')][hour] = consumption
            
        # Pro zítřek všechny hodiny
        tomorrow_type = 'weekend' if is_tomorrow_weekend else 'weekday'
        for hour in range(24):
            consumption = averages[tomorrow_type].get(hour, 0)
            prediction[tomorrow.strftime('%Y-%m-%d')][hour] = consumption
            
        logger.info(f"NAČÍTÁNÍ PREDIKCE SPOTŘEBY: Zpracováno {len(rows)} hodinových průměrů")
        
        return prediction
        
    except Exception as e:
        logger.error(f"CHYBA PŘI NAČÍTÁNÍ PREDIKCE SPOTŘEBY: {str(e)}")
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def predict_battery_state(house_id, house_data, solar_prediction, consumption_prediction):
    """
    Predikuje stav baterie pro každou budoucí hodinu na základě solární výroby a spotřeby.
    Vrací seznam predikcí stavu baterie pro každou hodinu.
    """
    try:
        # Aktuální stav baterie
        battery_level = house_data['current_battery_level']
        battery_capacity = house_data['battery_capacity']
        
        print(f"\nPREDIKCE STAVU BATERIE:")
        print(f"- Počáteční stav baterie: {battery_level:.2f} kWh / {battery_capacity:.2f} kWh ({battery_level/battery_capacity*100:.1f}%)")
        
        # Seřadíme všechny časové údaje
        all_hours = []
        for date_str, hours in consumption_prediction.items():
            for hour in hours.keys():
                all_hours.append((date_str, hour))
        all_hours.sort()
        
        print(f"- Predikce pro {len(all_hours)} hodin")
        
        # Pro každou hodinu spočítáme změnu stavu baterie
        battery_state = []
        for date_str, hour in all_hours:
            # Výchozí hodnoty
            solar_energy = 0
            consumption = consumption_prediction[date_str][hour]
            
            # Pokud máme solární výrobu pro tuto hodinu
            if date_str in solar_prediction and hour in solar_prediction[date_str]:
                solar_energy = solar_prediction[date_str][hour]
            
            # Změna stavu baterie
            net_change = (solar_energy - consumption) / 1000  # převod na kWh
            
            # Rozdělíme na nabíjení a vybíjení
            charged = max(0, net_change)
            discharged = abs(min(0, net_change))
            
            # Aktualizace stavu baterie
            old_level = battery_level
            battery_level = max(0, min(battery_capacity, battery_level + net_change))
            
            # Uložíme predikci
            battery_state.append({
                'date': date_str,
                'hour': hour,
                'solar_kwh': solar_energy / 1000,
                'consumption_kwh': consumption / 1000,
                'charged_kwh': charged,
                'discharged_kwh': discharged,
                'battery_level': battery_level,
                'datetime': f"{date_str} {hour:02d}:00"
            })
        
        return battery_state
        
    except Exception as e:
        logger.error(f"CHYBA PŘI PREDIKCI STAVU BATERIE: {str(e)}")
        raise

def optimize_charging(house_id, battery_state, price_data, house_data):
    """
    Optimalizuje plán nabíjení ze sítě na základě stavu baterie a cen elektřiny.
    Používá globální optimalizaci pro maximální využití nejlevnějších hodin.
    Zajišťuje, že stav baterie nikdy neklesne pod minimální úroveň.
    
    Args:
        house_id: ID domu
        battery_state: seznam predikcí stavu baterie
        price_data: slovník s cenami elektřiny
        house_data: slovník s daty o domu
        
    Returns:
        Seznam optimalizovaných plánů nabíjení pro každou hodinu
    """
    try:
        print("\n" + "="*80)
        print(f"OPTIMALIZACE NABÍJENÍ PRO DŮM {house_id}")
        print("="*80)
        
        logger.info(f"OPTIMALIZACE NABÍJENÍ: Začínám pro dům {house_id}")
        
        # Získání parametrů domu
        battery_capacity = house_data['battery_capacity']
        min_battery_level_percent = house_data['min_battery_level']
        min_battery_level = battery_capacity * (min_battery_level_percent / 100)
        max_charging_power = house_data['max_charging_power']
        charging_efficiency = house_data['charging_efficiency'] / 100
        risk_level = house_data['risk_level']
        
        # Nastavení parametrů podle rizikové úrovně
        target_level_percent = {
            'LOW': 80,      # Konzervativní - nabíjí až do 80% i za vyšší ceny
            'MEDIUM': 50,   # Vyvážené - nabíjí do 50%
            'HIGH': 30      # Agresivní - nabíjí jen do 30%, sází na levnější ceny později
        }[risk_level]
        
        # Výpočet cílového stavu baterie
        target_battery_level = battery_capacity * (target_level_percent / 100)
        
        print(f"\nPARAMETRY DOMU:")
        print(f"- Kapacita baterie: {battery_capacity} kWh")
        print(f"- Aktuální stav baterie: {house_data['current_battery_level']} kWh ({(house_data['current_battery_level']/battery_capacity*100):.1f}%)")
        print(f"- Minimální úroveň: {min_battery_level} kWh ({min_battery_level_percent}%)")
        print(f"- Cílová úroveň dle rizika '{risk_level}': {target_battery_level} kWh ({target_level_percent}%)")
        print(f"- Max. nabíjecí výkon: {max_charging_power} kW")
        print(f"- Účinnost nabíjení: {charging_efficiency*100}%")
        
        logger.info(f"OPTIMALIZACE NABÍJENÍ: Parametry - Kapacita: {battery_capacity}kWh, Min: {min_battery_level}kWh, " + 
                    f"Target: {target_battery_level}kWh, Max výkon: {max_charging_power}kW")
        
        # Simulovaný stav baterie pro každou hodinu bez dodatečného nabíjení
        simulated_battery_levels = [house_data['current_battery_level']]
        for i in range(1, len(battery_state)):
            # Předchozí stav + změna stavu v této hodině
            prev_level = simulated_battery_levels[-1]
            solar = battery_state[i]['solar_kwh']
            consumption = battery_state[i]['consumption_kwh']
            
            # Nový stav baterie po této hodině (bez dodatečného nabíjení)
            new_level = max(0, min(battery_capacity, prev_level + solar - consumption))
            simulated_battery_levels.append(new_level)
        
        # Výpis původní predikce stavu baterie
        print("\nPREDIKCE STAVU BATERIE BEZ DODATEČNÉHO NABÍJENÍ:")
        print("-" * 100)
        print(f"{'Datum a čas':<20} {'Solární energie':<18} {'Spotřeba':<14} {'Stav baterie':<16} {'Pod minimem':<15} {'Pod cílem':<15} {'Cena (Kč/kWh)':<15}")
        print("-" * 100)
        
        # Definice hodin pro analýzu
        hours_info = []
        for i, state in enumerate(battery_state):
            date_str = state['date']
            hour = state['hour']
            
            # Zjištění ceny pro tuto hodinu
            price = price_data.get(date_str, {}).get(hour, float('inf'))
            
            # Kontrola stavu baterie
            battery_level = simulated_battery_levels[i]
            under_min = "ANO" if battery_level < min_battery_level else "NE"
            under_target = "ANO" if battery_level < target_battery_level else "NE"
            
            hours_info.append({
                'index': i,
                'date': date_str,
                'hour': hour,
                'datetime': state['datetime'],
                'solar_kwh': state['solar_kwh'],
                'consumption_kwh': state['consumption_kwh'],
                'battery_level': battery_level,
                'under_min': battery_level < min_battery_level,
                'under_target': battery_level < target_battery_level,
                'price': price
            })
            
            print(f"{state['datetime']:<20} {state['solar_kwh']*1000:>6.1f} Wh        {state['consumption_kwh']*1000:>6.1f} Wh     {battery_level:>6.2f} kWh      {under_min:<15} {under_target:<15} {price:>6.2f} Kč/kWh")
        
        # Identifikace kritických bodů (kde baterie klesá pod minimum)
        critical_points = []
        for i in range(len(hours_info)):
            if hours_info[i]['under_min']:
                # Najdeme sekvenci kritických bodů
                sequence_start = i
                while i < len(hours_info) and hours_info[i]['under_min']:
                    i += 1
                sequence_end = i - 1
                
                # Nalezení minima v sekvenci
                min_level = min(hours_info[j]['battery_level'] for j in range(sequence_start, sequence_end + 1))
                min_idx = next(j for j in range(sequence_start, sequence_end + 1) 
                               if hours_info[j]['battery_level'] == min_level)
                
                critical_points.append({
                    'start_idx': sequence_start,
                    'end_idx': sequence_end,
                    'min_idx': min_idx,
                    'min_level': min_level,
                    'energy_needed': min_battery_level - min_level,
                    'hours': [hours_info[j] for j in range(sequence_start, sequence_end + 1)]
                })
        
        # Výpis kritických bodů
        if critical_points:
            print("\nKRITICKÉ BODY (SEKVENCE POD MINIMEM):")
            for i, point in enumerate(critical_points):
                print(f"Kritický bod #{i+1}: {hours_info[point['start_idx']]['datetime']} - " +
                      f"{hours_info[point['end_idx']]['datetime']} " +
                      f"(min: {point['min_level']:.2f} kWh, potřeba: {point['energy_needed']:.2f} kWh)")
        else:
            print("\nŽádné kritické body (baterie neklesá pod minimum).")
        
        # Vytvoření prázdného plánu nabíjení
        charging_plan = [{
            'date': state['date'],
            'hour': state['hour'],
            'planned_charging_kwh': 0,
            'reason': 'Není potřeba nabíjet'
        } for state in battery_state]
        
        # Kopie simulovaných stavů baterie pro aktualizaci během plánování
        updated_battery_levels = simulated_battery_levels.copy()
        
        # Funkce pro aktualizaci stavu baterie po naplánování nabíjení
        def update_battery_levels(start_idx, amount):
            """Aktualizuje stav baterie pro všechny hodiny od start_idx dále"""
            for j in range(start_idx, len(updated_battery_levels)):
                updated_battery_levels[j] += amount
        
        print("\nOPTIMALIZAČNÍ PLÁN PRO KRITICKÉ BODY:")
        
        # Zpracujeme každý kritický bod
        for point_idx, point in enumerate(critical_points):
            # Kolik energie potřebujeme dodat
            energy_needed = point['energy_needed']
            
            print(f"\nKritický bod #{point_idx+1}: Potřeba dobít {energy_needed:.2f} kWh do minima")
            
            # Najdeme všechny dostupné hodiny před tímto kritickým bodem
            available_hours = []
            for i in range(point['start_idx']):
                space_available = min(
                    battery_capacity - updated_battery_levels[i],  # Dostupné místo v baterii
                    max_charging_power  # Maximální nabíjecí výkon
                )
                
                if space_available >= 0.1:  # Ignorujeme zanedbatelné množství
                    available_hours.append({
                        'index': i,
                        'date': hours_info[i]['date'],
                        'hour': hours_info[i]['hour'],
                        'datetime': hours_info[i]['datetime'],
                        'price': hours_info[i]['price'],
                        'space_available': space_available
                    })
            
            # Pokud nejsou dostupné žádné hodiny před tímto bodem (např. je na začátku dne),
            # musíme použít hodiny v předchozím dni (pokud jsou k dispozici)
            if len(available_hours) == 0:
                print(f"  Varování: Nebyla nalezena žádná dostupná hodina před kritickým bodem!")
                print(f"  Pro tento případ bude použito nouzové nabíjení za jakoukoliv cenu")
                
                # Nastavíme nouzové nabíjení v poslední možné hodině před kritickým bodem
                emergency_idx = max(0, point['start_idx'] - 1)
                emergency_amount = min(
                    energy_needed,
                    max_charging_power,
                    battery_capacity - updated_battery_levels[emergency_idx]
                )
                
                if emergency_amount > 0:
                    charging_plan[emergency_idx]['planned_charging_kwh'] = emergency_amount
                    charging_plan[emergency_idx]['reason'] = f"NOUZOVÉ NABÍJENÍ: baterie pod min. úrovní ({min_battery_level} kWh)"
                    
                    # Aktualizujeme stav baterie
                    update_battery_levels(emergency_idx, emergency_amount)
                    
                    print(f"  Nouzové nabíjení: {hours_info[emergency_idx]['datetime']} - {emergency_amount:.2f} kWh")
                    
                    # Přepočítáme energii potřebnou pro další kritické body
                    for future_point in critical_points[point_idx+1:]:
                        for j in range(future_point['start_idx'], future_point['end_idx'] + 1):
                            if updated_battery_levels[j] < min_battery_level:
                                future_point['energy_needed'] = min_battery_level - min(
                                    updated_battery_levels[k] for k in range(future_point['start_idx'], future_point['end_idx'] + 1)
                                )
                                break
                            else:
                                future_point['energy_needed'] = 0
            else:
                # Seřadíme dostupné hodiny podle ceny
                available_hours.sort(key=lambda x: x['price'])
                
                print(f"  Dostupné hodiny před kritickým bodem (seřazené podle ceny):")
                for i, hour in enumerate(available_hours[:5]):  # Zobrazíme jen prvních 5 pro přehlednost
                    print(f"  {i+1}. {hour['datetime']} - {hour['price']:.2f} Kč/kWh (prostor: {hour['space_available']:.2f} kWh)")
                if len(available_hours) > 5:
                    print(f"  ... a dalších {len(available_hours) - 5} hodin")
                
                # Plánujeme nabíjení
                energy_to_plan = energy_needed
                for hour in available_hours:
                    if energy_to_plan <= 0:
                        break
                        
                    idx = hour['index']
                    
                    # Zjistíme, zda už máme něco naplánované
                    existing_plan = charging_plan[idx]['planned_charging_kwh']
                    
                    # Kolik více můžeme naplánovat
                    additional_capacity = min(
                        max_charging_power - existing_plan,  # Kolik více můžeme nabíjet
                        hour['space_available']  # Dostupné místo v baterii
                    )
                    
                    # Kolik naplánujeme
                    plan_amount = min(energy_to_plan, additional_capacity)
                    
                    if plan_amount > 0.1:  # Ignorujeme zanedbatelné množství
                        # Aktualizujeme plán
                        new_total = existing_plan + plan_amount
                        charging_plan[idx]['planned_charging_kwh'] = new_total
                        
                        # Při první změně nastavíme důvod
                        if existing_plan == 0:
                            charging_plan[idx]['reason'] = f"Baterie pod min. úrovní ({min_battery_level} kWh)"
                        
                        # Aktualizujeme zbývající energii k plánování
                        energy_to_plan -= plan_amount
                        
                        # Aktualizujeme stav baterie
                        update_battery_levels(idx, plan_amount)
                        
                        print(f"  {hours_info[idx]['datetime']}: {'Navýšeno na' if existing_plan > 0 else 'Naplánováno'} {new_total:.2f} kWh (cena: {hour['price']:.2f} Kč/kWh)")
                
                # Kontrola, zda jsme naplánovali dostatek energie
                if energy_to_plan > 0.1:
                    print(f"  Varování: Nepodařilo se naplánovat {energy_to_plan:.2f} kWh z {energy_needed:.2f} kWh!")
                    
                    # Nouzové nabíjení v poslední možné hodině před kritickým bodem
                    emergency_idx = max(0, point['start_idx'] - 1)
                    emergency_amount = min(
                        energy_to_plan,
                        max_charging_power - charging_plan[emergency_idx]['planned_charging_kwh'],
                        battery_capacity - updated_battery_levels[emergency_idx]
                    )
                    
                    if emergency_amount > 0.1:
                        new_total = charging_plan[emergency_idx]['planned_charging_kwh'] + emergency_amount
                        charging_plan[emergency_idx]['planned_charging_kwh'] = new_total
                        charging_plan[emergency_idx]['reason'] = f"NOUZOVÉ NABÍJENÍ: baterie pod min. úrovní ({min_battery_level} kWh)"
                        
                        # Aktualizujeme stav baterie
                        update_battery_levels(emergency_idx, emergency_amount)
                        
                        print(f"  Nouzové nabíjení: {hours_info[emergency_idx]['datetime']} - navýšeno na {new_total:.2f} kWh")
            
            # Přepočítáme energii potřebnou pro další kritické body
            for future_point in critical_points[point_idx+1:]:
                min_level_in_point = min(updated_battery_levels[j] for j in range(future_point['start_idx'], future_point['end_idx'] + 1))
                if min_level_in_point < min_battery_level:
                    future_point['energy_needed'] = min_battery_level - min_level_in_point
                else:
                    future_point['energy_needed'] = 0
        
        # Určíme nejnižší úroveň baterie po vyřešení kritických bodů
        lowest_level = min(updated_battery_levels)
        
        # Naplánování nabíjení na cílovou úroveň, pouze pokud je pod cílovou úrovní
        target_energy_needed = 0
        if lowest_level < target_battery_level:
            target_energy_needed = target_battery_level - lowest_level
            
            print(f"\nPLÁNOVÁNÍ NABÍJENÍ NA CÍLOVOU ÚROVEŇ:")
            print(f"Nejnižší úroveň baterie: {lowest_level:.2f} kWh, cílová úroveň: {target_battery_level:.2f} kWh")
            print(f"Potřebujeme dobít: {target_energy_needed:.2f} kWh")
            
            # Najdeme všechny dostupné hodiny
            available_hours = []
            for i in range(len(hours_info)):
                # Kolik více můžeme naplánovat v této hodině
                existing_plan = charging_plan[i]['planned_charging_kwh']
                additional_capacity = min(
                    max_charging_power - existing_plan,  # Kolik více můžeme nabíjet
                    battery_capacity - updated_battery_levels[i]  # Dostupné místo v baterii
                )
                
                if additional_capacity >= 0.1:  # Ignorujeme zanedbatelné množství
                    available_hours.append({
                        'index': i,
                        'date': hours_info[i]['date'],
                        'hour': hours_info[i]['hour'],
                        'datetime': hours_info[i]['datetime'],
                        'price': hours_info[i]['price'],
                        'additional_capacity': additional_capacity
                    })
            
            # Seřadíme dostupné hodiny podle ceny
            available_hours.sort(key=lambda x: x['price'])
            
            print(f"Dostupné hodiny pro nabíjení na cílovou úroveň (seřazené podle ceny):")
            for i, hour in enumerate(available_hours[:5]):  # Zobrazíme jen prvních 5 pro přehlednost
                print(f"{i+1}. {hour['datetime']} - {hour['price']:.2f} Kč/kWh (prostor: {hour['additional_capacity']:.2f} kWh)")
            if len(available_hours) > 5:
                print(f"... a dalších {len(available_hours) - 5} hodin")
            
            # Plánujeme nabíjení
            energy_to_plan = target_energy_needed
            for hour in available_hours:
                if energy_to_plan <= 0:
                    break
                    
                idx = hour['index']
                
                # Zjistíme, zda už máme něco naplánované
                existing_plan = charging_plan[idx]['planned_charging_kwh']
                
                # Kolik naplánujeme
                plan_amount = min(energy_to_plan, hour['additional_capacity'])
                
                if plan_amount > 0.1:  # Ignorujeme zanedbatelné množství
                    # Aktualizujeme plán
                    new_total = existing_plan + plan_amount
                    charging_plan[idx]['planned_charging_kwh'] = new_total
                    
                    # Při první změně nastavíme důvod
                    if existing_plan == 0:
                        charging_plan[idx]['reason'] = f"Dobíjení na cílovou úroveň ({target_battery_level} kWh)"
                    
                    # Aktualizujeme zbývající energii k plánování
                    energy_to_plan -= plan_amount
                    
                    # Aktualizujeme stav baterie
                    update_battery_levels(idx, plan_amount)
                    
                    print(f"{hours_info[idx]['datetime']}: {'Navýšeno na' if existing_plan > 0 else 'Naplánováno'} {new_total:.2f} kWh (cena: {hour['price']:.2f} Kč/kWh)")
            
            if energy_to_plan > 0.1:
                print(f"Pro cílovou úroveň naplánováno pouze {target_energy_needed - energy_to_plan:.2f} z {target_energy_needed:.2f} kWh")
            else:
                print(f"Úspěšně naplánováno {target_energy_needed:.2f} kWh pro dosažení cílové úrovně")
        else:
            print(f"\nNabíjení na cílovou úroveň není potřeba. Nejnižší úroveň baterie ({lowest_level:.2f} kWh) je nad cílovou úrovní ({target_battery_level:.2f} kWh).")
        
        # Zkontrolujeme, zda po všech úpravách stále neklesne baterie pod minimum
        remaining_critical = False
        for i, level in enumerate(updated_battery_levels):
            if level < min_battery_level:
                if not remaining_critical:
                    print(f"\nVAROVÁNÍ: I po optimalizaci existují hodiny pod minimální úrovní:")
                    remaining_critical = True
                
                print(f"{hours_info[i]['datetime']}: {level:.2f} kWh < {min_battery_level:.2f} kWh (min)")
        
        if not remaining_critical:
            print(f"\nOPTIMALIZACE ÚSPĚŠNÁ: Baterie nikdy neklesne pod minimální úroveň.")
        
        # Výpis finálního stavu baterie a plánu nabíjení
        print("\nFINÁLNÍ STAV BATERIE PO NAPLÁNOVANÉM NABÍJENÍ:")
        print("-" * 80)
        print(f"{'Datum a čas':<20} {'Původní stav':<15} {'Nový stav':<15} {'Plánované nabíjení':<20}")
        print("-" * 80)
        
        for i in range(len(hours_info)):
            original_level = simulated_battery_levels[i]
            updated_level = updated_battery_levels[i]
            planned = charging_plan[i]['planned_charging_kwh']
            
            plan_str = f"{planned:.2f} kWh" if planned > 0 else "0 kWh"
            print(f"{hours_info[i]['datetime']:<20} {original_level:>6.2f} kWh      {updated_level:>6.2f} kWh      {plan_str:<20}")
        
        # Výpis finálního plánu nabíjení
        print("\nVYTVÁŘÍM OPTIMALIZOVANÝ PLÁN NABÍJENÍ:")
        print("-" * 80)
        print(f"{'Datum a čas':<20} {'Plánované nabíjení':<20} {'Důvod':<40}")
        print("-" * 80)
        
        # Upravíme plán na standardní formát a vypíšeme
        final_plan = []
        for i, plan in enumerate(charging_plan):
            date_str = plan['date']
            hour = plan['hour']
            planned_charging = plan['planned_charging_kwh']
            reason = plan['reason']
            
            final_plan.append({
                'date': date_str,
                'hour': hour,
                'planned_charging_kwh': planned_charging
            })
            
            # Výpis plánu
            plan_str = f"{planned_charging:.2f} kWh" if planned_charging > 0 else "0 kWh (nenabíjí se)"
            print(f"{date_str} {hour:02d}:00   {plan_str:<20} {reason:<40}")
        
        # Součet celkového nabíjení
        total_planned = sum(plan['planned_charging_kwh'] for plan in charging_plan)
        print(f"\nCELKOVÉ PLÁNOVANÉ NABÍJENÍ: {total_planned:.2f} kWh")
        
        logger.info(f"OPTIMALIZACE NABÍJENÍ: Vytvořen plán pro {len(charging_plan)} hodin, celkem {total_planned:.2f} kWh")
        
        return final_plan
        
    except Exception as e:
        logger.error(f"CHYBA PŘI OPTIMALIZACI NABÍJENÍ: {str(e)}")
        raise

def save_charging_schedule(house_id, charging_plan):
    """
    Uloží plán nabíjení do databáze.
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
        for plan in charging_plan:
            if plan['planned_charging_kwh'] > 0:
                cur.execute("""
                    INSERT INTO api_chargingschedule
                    (house_id, date, hour, planned_charging_kwh)
                    VALUES (%s, %s, %s, %s)
                """, [
                    house_id,
                    plan['date'],
                    plan['hour'],
                    plan['planned_charging_kwh']
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
    
    print("UKLÁDÁNÍ PLÁNU DO DATABÁZE ZATÍM ZAKOMENTOVÁNO PRO TESTOVÁNÍ")

def plan_charging_for_house(house_id):
    """
    Kompletní proces plánování nabíjení pro jeden dům.
    """
    try:
        print("\n" + "*"*100)
        print(f"ZAČÁTEK PLÁNOVÁNÍ NABÍJENÍ PRO DŮM {house_id}")
        print("*"*100)
        
        # 1. Získání dat o domu
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
            
        # 2. Získání predikce solární výroby
        print("\nKROK 2: ZÍSKÁNÍ PREDIKCE SOLÁRNÍ VÝROBY")
        solar_prediction = get_solar_prediction(
            house_power=house_data['solar_power'],
            charging_efficiency=house_data['charging_efficiency']
        )
        
        if not solar_prediction:
            print("VAROVÁNÍ: Žádná data o solární výrobě nebyla nalezena!")
        else:
            days = len(solar_prediction)
            total_hours = sum(len(hours) for hours in solar_prediction.values()),
            print(f"Úspěšně načtena predikce solární výroby pro {days} dnů ({total_hours} hodin)")

        # 3. Získání predikce spotřeby
        print("\nKROK 3: ZÍSKÁNÍ PREDIKCE SPOTŘEBY")
        consumption_prediction = get_consumption_prediction(house_id)
        
        if not consumption_prediction:
            print("VAROVÁNÍ: Žádná data o spotřebě nebyla nalezena!")
        else:
            days = len(consumption_prediction)
            total_hours = sum(len(hours) for hours in consumption_prediction.values())
            print(f"Úspěšně načtena predikce spotřeby pro {days} dnů ({total_hours} hodin)")
            
        
        # 4. Získání cen elektřiny
        print("\nKROK 4: ZÍSKÁNÍ CEN ELEKTŘINY")
        price_data = get_price_data()
        
        if not price_data:
            print("VAROVÁNÍ: Žádná data o cenách elektřiny nebyla nalezena!")
        else:
            days = len(price_data)
            total_hours = sum(len(hours) for hours in price_data.values())
            print(f"Úspěšně načteny ceny elektřiny pro {days} dnů ({total_hours} hodin)")
            
            # Ukázka cen
            print("\nUkázka cen elektřiny (10 nejlevnějších hodin):")
            flat_prices = []
            for date_str, hours in price_data.items():
                for hour, price in hours.items():
                    flat_prices.append((date_str, hour, price))
            
            flat_prices.sort(key=lambda x: x[2])
            for date_str, hour, price in flat_prices[:10]:
                print(f"{date_str} {hour:02d}:00: {price:.3f} Kč/kWh")
        
        # 5. Predikce stavu baterie
        print("\nKROK 5: PREDIKCE STAVU BATERIE")
        battery_state = predict_battery_state(
            house_id,
            house_data,
            solar_prediction,
            consumption_prediction
        )
        
        # 6. Optimalizace plánu nabíjení
        print("\nKROK 6: OPTIMALIZACE PLÁNU NABÍJENÍ")
        charging_plan = optimize_charging(
            house_id,
            battery_state,
            price_data,
            house_data
        )
        
        # 7. Uložení plánu do databáze
        print("\nKROK 7: ULOŽENÍ PLÁNU DO DATABÁZE")
        print("UKLÁDÁNÍ PLÁNU DO DATABÁZE ZATÍM ZAKOMENTOVÁNO PRO TESTOVÁNÍ")
        # save_charging_schedule(house_id, charging_plan)
        
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
        
        