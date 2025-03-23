import psycopg2
from datetime import datetime
import logging
import json
import random

logging.basicConfig(
   level=logging.INFO,
   format='[%(asctime)s] %(levelname)s: %(message)s',
   filename='/app/logs/django.log',
   filemode='a'
)

logger = logging.getLogger('api')

def is_peak_time(current_time, is_weekend):
   """
   Určí, zda je aktuální čas ve špičce podle dne v týdnu
   """
   hour = current_time.hour
   
   if is_weekend:
       # Víkendové špičky: 8-10, 11-13, 17-20
       return (8 <= hour < 10) or (11 <= hour < 13) or (17 <= hour < 20)
   else:
       # Špičky ve všední dny: 6-8, 17-20
       return (6 <= hour < 8) or (17 <= hour < 20)

def get_adjusted_duration(min_duration, max_duration, is_peak_time, for_active_state):
   """
   Upraví délku běhu/standby podle toho, zda je špička a podle typu stavu
   """
   if is_peak_time:
       if for_active_state:
           # Ve špičce prodloužíme aktivní běh - použijeme horní polovinu rozsahu
           range_size = max_duration - min_duration
           half_range = range_size // 2
           adjusted_min = min_duration + half_range
           adjusted_max = max_duration
       else:
           # Ve špičce zkrátíme standby NA POLOVINU
           adjusted_min = min_duration // 2
           adjusted_max = max_duration // 2
   else:
       # Mimo špičku použijeme celý rozsah
       adjusted_min = min_duration
       adjusted_max = max_duration
       
   return random.randint(adjusted_min, adjusted_max)

def simulate_minute_consumption():
   try:
       logger.info("ZAHAJUJI SIMULACI SPOTŘEBY")
       conn = psycopg2.connect(
           dbname="fve_db",
           user="postgres",
           password="heslo",
           host="db"
       )
       cur = conn.cursor()

       current_time = datetime.now().replace(second=0, microsecond=0)
       current_date = current_time.date()
       current_time_str = current_time.strftime('%H:%M')
       current_hour = current_time.hour
       current_minute = current_time.minute
       is_weekend = current_time.weekday() >= 5
       logger.info(f"Simuluji pro čas: {current_date} {current_time_str} ({'víkend' if is_weekend else 'pracovní den'})")
       
       # Zjistíme, které speciální domy jsou aktivní
       cur.execute("""
           SELECT id FROM api_house
           WHERE is_active = true AND id IN (9, 999, 9999, 99999)
       """)
       special_house_ids = [row[0] for row in cur.fetchall()]
       logger.info(f"Aktivní speciální domy: {special_house_ids}")
       
       # Načteme informace o EXTREME domech pro novou funkcionalitu
       cur.execute("""
           SELECT id, risk_level 
           FROM api_house
           WHERE is_active = true
       """)
       house_risk_levels = {row[0]: row[1] for row in cur.fetchall()}
       extreme_house_ids = [id for id, level in house_risk_levels.items() if level == 'EXTREME']
       logger.info(f"Nalezeno {len(extreme_house_ids)} EXTREME domů: {extreme_house_ids}")
       
       # Načteme všechny spotřebiče pro všechny aktivní domy
       cur.execute("""
           SELECT 
               h.id as house_id,
               a.id as appliance_id,
               a.power_consumption,
               a.standby_power,
               a.appliance_type,
               a.is_active,
               a.in_standby,
               a.remaining_minutes,
               a.run_duration_min,
               a.run_duration_max,
               a.pause_duration_min,
               a.pause_duration_max,
               a.next_start_time,
               a.usage_duration_min,
               a.usage_duration_max,
               a.weekday_hours,
               a.weekend_hours,
               a.remaining_minutes_list,
               a.planned_starts,
               a.inactive_windows,
               a.interruptible
           FROM api_house h
           JOIN api_appliance a ON 
               CASE 
                   WHEN h.id = 99 THEN a.house_id = 9  -- Pro dům 99 používáme spotřebiče domu 9
                   ELSE a.house_id = h.id              -- Pro ostatní domy používáme jejich vlastní spotřebiče
               END
           WHERE h.is_active = true
       """)
       rows = cur.fetchall()
       logger.info(f"Nalezeno {len(rows)} spotřebičů pro všechny aktivní domy")
       
       # Pro každý dům sledujeme seznam spotřebičů a celkovou spotřebu
       houses = {}
       for (house_id, appliance_id, power, standby_power, app_type, is_active, 
            in_standby, remaining_minutes, run_duration_min, run_duration_max, 
            pause_duration_min, pause_duration_max, next_start_time,
            usage_duration_min, usage_duration_max, weekday_hours, weekend_hours,
            remaining_minutes_list, planned_starts, inactive_windows, interruptible) in rows:
           
           # Vytvoříme nový záznam pro dům pokud neexistuje
           if house_id not in houses:
               houses[house_id] = {
                   'appliances': [],  # Seznam spotřebičů
                   'total_wh': 0      # Celková spotřeba ve Wh
               }
           
           # NOVÁ FUNKCE - Kontrola inactive_windows pro EXTREME domy
           is_inactive = False
           if house_id in extreme_house_ids and app_type in ['CONSTANT', 'CYCLIC'] and inactive_windows:
               # Převedeme inactive_windows z JSON na Python objekt, pokud je to potřeba
               if isinstance(inactive_windows, str):
                   inactive_windows = json.loads(inactive_windows)
                
               # Kontrola, zda aktuální čas odpovídá některému oknu neaktivity
               for window in inactive_windows:
                   # Formát s 'start_date' a 'end_date'
                   start_date = window.get('start_date')
                   end_date = window.get('end_date', start_date)  # Výchozí hodnota je start_date pokud end_date chybí
                   
                   # Pokud máme definovaná data, kontrolujeme, zda aktuální datum je v rozsahu
                   start_date_obj = None
                   end_date_obj = None
                   
                   if start_date:
                       start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                   if end_date:
                       end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                   
                   # Kontrola, zda aktuální datum je v rozsahu
                   if start_date_obj and end_date_obj:
                       if not (start_date_obj <= current_date <= end_date_obj):
                           continue
                   elif start_date_obj:
                       if current_date != start_date_obj:
                           continue
                   
                   # Kontrola hodin
                   start_hour = window.get('start_hour', 0)
                   end_hour = window.get('end_hour', 0)
                   
                   # Speciální zpracování pro okna přes půlnoc
                   if start_hour > end_hour:
                       # Kontrola, zda jsme v první části okna (večer) nebo v druhé části (ráno)
                       if current_date == start_date_obj and current_hour >= start_hour:
                           # Jsme ve večerní části okna (první den)
                           is_inactive = True
                           logger.info(f"Spotřebič {appliance_id} ({app_type}) v domě {house_id} je vypnutý (čas {current_hour} je v neaktivním okně {start_hour}-{end_hour} přes půlnoc, večerní část)")
                           break
                       elif current_date == end_date_obj and current_hour < end_hour:
                           # Jsme v ranní části okna (druhý den)
                           is_inactive = True
                           logger.info(f"Spotřebič {appliance_id} ({app_type}) v domě {house_id} je vypnutý (čas {current_hour} je v neaktivním okně {start_hour}-{end_hour} přes půlnoc, ranní část)")
                           break
                   else:
                       # Standardní případ - v rámci jednoho dne
                       if start_hour <= current_hour < end_hour:
                           is_inactive = True
                           logger.info(f"Spotřebič {appliance_id} ({app_type}) v domě {house_id} je vypnutý (čas {current_hour} je v neaktivním okně {start_hour}-{end_hour})")
                           break
               
           # Spočítáme spotřebu pro každý typ spotřebiče
           if is_inactive:
               # Spotřebič je v neaktivním okně (pouze pro EXTREME domy)
               minute_consumption = 0
               logger.info(f"Spotřebič {appliance_id} ({app_type}) v domě {house_id} je v neaktivním okně - spotřeba 0W")
           elif app_type == 'CONSTANT':
               variation = random.uniform(0.9, 1.0)
               minute_consumption = (power * variation) / 60
               logger.debug(f"Spotřebič {appliance_id} (CONSTANT): {minute_consumption}W/min (variation: {variation:.2f})")
               
           elif app_type == 'CYCLIC':
               if remaining_minutes == 0:
                   peak_time = is_peak_time(current_time, is_weekend)
                   
                   if in_standby:
                       new_remaining = get_adjusted_duration(
                           run_duration_min,
                           run_duration_max,
                           peak_time,
                           for_active_state=True
                       )
                       cur.execute("""
                           UPDATE api_appliance 
                           SET is_active = true,
                               in_standby = false,
                               remaining_minutes = %s
                           WHERE id = %s
                       """, [new_remaining, appliance_id])
                       is_active = True
                       in_standby = False
                   else:
                       new_remaining = get_adjusted_duration(
                           pause_duration_min,
                           pause_duration_max,
                           peak_time,
                           for_active_state=False
                       )
                       cur.execute("""
                           UPDATE api_appliance 
                           SET is_active = false,
                               in_standby = true,
                               remaining_minutes = %s
                           WHERE id = %s
                       """, [new_remaining, appliance_id])
                       is_active = False
                       in_standby = True
                   
                   logger.debug(f"Spotřebič {appliance_id} změnil stav, nový čas: {new_remaining}min (špička: {peak_time})")
                   remaining_minutes = new_remaining
               
               if is_active:
                   variation = random.uniform(0.9, 1.0)
                   minute_consumption = (power * variation) / 60
               else:
                   minute_consumption = standby_power / 60
               logger.debug(f"Spotřebič {appliance_id} (CYCLIC): {minute_consumption}W/min (Active: {is_active})")
               
               if remaining_minutes > 0:
                   cur.execute("""
                       UPDATE api_appliance 
                       SET remaining_minutes = remaining_minutes - 1
                       WHERE id = %s
                   """, [appliance_id])

           elif app_type == 'SCHEDULED':
               # NOVÁ FUNKCE - Kontrola, zda běžící spotřebič není v neaktivním okně
               if remaining_minutes > 0:
                   # Kontrola, zda je v neaktivním okně a zda je přerušitelný
                   is_extreme_house = house_id in extreme_house_ids
                   should_interrupt = False
                   
                   if is_extreme_house:
                       # Kontrola, zda je běžící spotřebič v neaktivním okně
                       windows = weekend_hours if is_weekend else weekday_hours
                       if windows:
                           for window in windows:
                               # Kontrola, zda je aktuální hodina v tomto okně
                               start_hour = window.get('start', 0)
                               end_hour = window.get('end', 0)
                               
                               # Pro okna přes půlnoc
                               if start_hour > end_hour:
                                   # Jsme buď ve večerní nebo ranní části
                                   if (current_hour >= start_hour) or (current_hour < end_hour):
                                       # Kontrola, zda je okno neaktivní
                                       if not window.get('is_active', True):
                                           should_interrupt = True
                                           break
                               else:
                                   # Standardní případ v rámci jednoho dne
                                   if start_hour <= current_hour < end_hour:
                                       # Kontrola, zda je okno neaktivní
                                       if not window.get('is_active', True):
                                           should_interrupt = True
                                           break
                   
                   if should_interrupt and interruptible:
                       # Přerušíme běh, pokud je v neaktivním okně a je přerušitelný
                       minute_consumption = standby_power / 60 if standby_power else 0
                       logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (SCHEDULED): Přerušen běh v neaktivním okně (interruptible)")
                       
                       # Nastavíme remaining_minutes na 0 místo dekrementace
                       cur.execute("""
                           UPDATE api_appliance 
                           SET remaining_minutes = 0
                           WHERE id = %s
                       """, [appliance_id])
                   else:
                       # Normální chování - spotřebič běží
                       variation = random.uniform(0.9, 1.0)
                       minute_consumption = (power * variation) / 60
                       logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): {minute_consumption}W/min (Zbývá: {remaining_minutes}min)")
                       
                       # Snížíme remaining_minutes jen pokud neinterrumpujeme
                       cur.execute("""
                           UPDATE api_appliance 
                           SET remaining_minutes = remaining_minutes - 1
                           WHERE id = %s
                       """, [appliance_id])
               else:
                   minute_consumption = standby_power / 60 if standby_power else 0
                   logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): {minute_consumption}W/min (Standby)")

                   # UPRAVENO: Kontrola is_active u okna při spuštění spotřebiče
                   if next_start_time and current_time.replace(tzinfo=None) == next_start_time.replace(tzinfo=None):
                       # Kontrola, zda okno je aktivní (pouze pro EXTREME domy)
                       is_extreme_house = house_id in extreme_house_ids
                       should_skip = False
                       
                       if is_extreme_house:
                           windows = weekend_hours if is_weekend else weekday_hours
                           if windows:
                               for window in windows:
                                   # Zjistit, do kterého okna patří aktuální čas
                                   start_hour = window.get('start', 0)
                                   end_hour = window.get('end', 0)
                                   
                                   # Pro okna přes půlnoc
                                   if start_hour > end_hour:
                                       # Jsme buď ve večerní nebo ranní části
                                       if (current_hour >= start_hour) or (current_hour < end_hour):
                                           # Kontrola, zda je okno neaktivní
                                           if not window.get('is_active', True):
                                               should_skip = True
                                               logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (SCHEDULED): Přeskakuji naplánované spuštění v {current_time_str}, okno je neaktivní")
                                               break
                                   else:
                                       # Standardní případ v rámci jednoho dne
                                       if start_hour <= current_hour < end_hour:
                                           # Kontrola, zda je okno neaktivní
                                           if not window.get('is_active', True):
                                               should_skip = True
                                               logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (SCHEDULED): Přeskakuji naplánované spuštění v {current_time_str}, okno je neaktivní")
                                               break
                       
                       # Pouze pokud nemáme přeskočit, spustíme spotřebič
                       if not should_skip:
                           duration = random.randint(usage_duration_min, usage_duration_max)
                           cur.execute("""
                               UPDATE api_appliance 
                               SET remaining_minutes = %s,
                                   next_start_time = NULL
                               WHERE id = %s
                           """, [duration, appliance_id])
                           logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): Spuštěn běh na {duration}min")
                       else:
                           # Pouze vynulujeme next_start_time
                           cur.execute("""
                               UPDATE api_appliance 
                               SET next_start_time = NULL
                               WHERE id = %s
                           """, [appliance_id])
                           logger.info(f"Spotřebič {appliance_id} (SCHEDULED): Naplánované spuštění přeskočeno (neaktivní okno)")

               # NOVÝ KÓD - Kontrola pro EXTREME domy, zda jsme minutu po konci neaktivního okna
               if current_minute == 1 and house_id in extreme_house_ids:
                   windows = weekend_hours if is_weekend else weekday_hours
                   if windows:
                       changed = False
                       for i, window in enumerate(windows):
                           # Kontrola, zda jsme minutu po konci okna a zda je okno neaktivní
                           end_hour = window.get('end', 0)
                           is_window_active = window.get('is_active', True)
                           
                           if not is_window_active and current_hour == end_hour:
                               # Aktivujeme okno
                               windows[i]['is_active'] = True
                               changed = True
                               logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (SCHEDULED): Okno {window['start']}:00-{window['end']}:00 znovu aktivováno v {current_hour}:01")
                       
                       if changed:
                           # Uložíme změněná data zpět do databáze
                           update_field = 'weekend_hours' if is_weekend else 'weekday_hours'
                           cur.execute(f"""
                               UPDATE api_appliance 
                               SET {update_field} = %s::jsonb
                               WHERE id = %s
                           """, [json.dumps(windows), appliance_id])

               # Plánování na další hodinu (v 59. minutě)
               if current_minute == 59:
                   next_hour = (current_hour + 1) % 24
                   windows = weekend_hours if is_weekend else weekday_hours
                   
                   if windows:
                       for i, window in enumerate(windows):
                           if window['start'] == next_hour:
                               # EXTREME logika pro kontrolu is_active u SCHEDULED
                               is_extreme_house = house_id in extreme_house_ids
                               is_window_active = window.get('is_active', True)
                               
                               if is_extreme_house and not is_window_active:
                                   # Pro neaktivní okno pouze přeskočíme plánování
                                   logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (SCHEDULED): Přeskakuji plánování pro neaktivní okno {window['start']}:00-{window['end']}:00")
                                   continue  # Přeskočíme plánování pro toto okno
                               
                               # Původní logika pro plánování
                               if random.random() < window['probability']:
                                   start_minutes = window['start'] * 60
                                   end_minutes = window['end'] * 60
                                   if end_minutes < start_minutes:
                                       end_minutes += 24 * 60

                                   if remaining_minutes > 0:
                                       earliest_start = start_minutes + remaining_minutes
                                       if earliest_start < end_minutes:
                                           random_minute = random.randint(earliest_start, end_minutes)
                                       else:
                                           continue
                                   else:
                                       random_minute = random.randint(start_minutes, end_minutes)

                                   target_hour = (random_minute // 60) % 24
                                   target_minute = random_minute % 60
                                   
                                   next_start = current_time.replace(
                                       hour=target_hour,
                                       minute=target_minute
                                   )

                                   cur.execute("""
                                       UPDATE api_appliance 
                                       SET next_start_time = %s
                                       WHERE id = %s
                                   """, [next_start, appliance_id])
                                   logger.debug(f"Spotřebič {appliance_id} (SCHEDULED): Naplánován na {next_start}")
                                   break

           elif app_type == 'ON_DEMAND':
               remaining_minutes_list = [] if remaining_minutes_list is None else remaining_minutes_list
               planned_starts = [] if planned_starts is None else planned_starts

               minute_consumption = 0
               new_remaining_minutes = []
               
               # NOVÁ FUNKCE - Kontrola, zda běžící spotřebiče nejsou v neaktivním okně
               is_extreme_house = house_id in extreme_house_ids
               should_interrupt = False
               
               if is_extreme_house:
                   # Kontrola, zda je běžící spotřebič v neaktivním okně
                   windows = weekend_hours if is_weekend else weekday_hours
                   if windows:
                       for window in windows:
                           # Kontrola, zda je aktuální hodina v tomto okně
                           start_hour = window.get('start', 0)
                           end_hour = window.get('end', 0)
                           
                           # Pro okna přes půlnoc
                           if start_hour > end_hour:
                               # Jsme buď ve večerní nebo ranní části
                               if (current_hour >= start_hour) or (current_hour < end_hour):
                                   # Kontrola, zda je okno neaktivní
                                   if not window.get('is_active', True):
                                       should_interrupt = True
                                       break
                           else:
                               # Standardní případ v rámci jednoho dne
                               if start_hour <= current_hour < end_hour:
                                   # Kontrola, zda je okno neaktivní
                                   if not window.get('is_active', True):
                                       should_interrupt = True
                                       break
               
               # Zpracování běžících spotřebičů
               for mins in remaining_minutes_list:
                   if mins > 0:
                       # Pokud je to přerušitelný spotřebič a měl by být přerušen, přeskočíme spotřebu a nepřidáme do nového seznamu
                       if should_interrupt and interruptible:
                           # Nepřidáváme do seznamu - efektivně ukončíme běh
                           logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (ON_DEMAND): Přerušen běh v neaktivním okně (interruptible)")
                       else:
                           # Normální chování - spotřebič běží
                           variation = random.uniform(0.9, 1.0)
                           minute_consumption += (power * variation) / 60
                           new_remaining_minutes.append(mins - 1)
                   
               new_planned_starts = []
               current_time_str_full = current_time.strftime('%Y-%m-%d %H:%M:%S')
               
               # UPRAVENO: Kontrola is_active u okna při spuštění spotřebiče
               for start in planned_starts:
                   if start == current_time_str_full:
                       # Kontrola, zda okno je aktivní (pouze pro EXTREME domy)
                       should_skip = False
                       
                       if is_extreme_house:
                           # V tomto případě již víme, zda jsme v neaktivním okně díky předchozí kontrole
                           if should_interrupt:
                               should_skip = True
                               logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (ON_DEMAND): Přeskakuji naplánované spuštění v {current_time_str}, okno je neaktivní")
                       
                       # Pouze pokud nemáme přeskočit, spustíme spotřebič
                       if not should_skip:
                           duration = random.randint(usage_duration_min, usage_duration_max)
                           new_remaining_minutes.append(duration)
                           logger.debug(f"Spotřebič {appliance_id} (ON_DEMAND): Spuštěn nový běh na {duration}min")
                       else:
                           logger.info(f"Spotřebič {appliance_id} (ON_DEMAND): Naplánované spuštění přeskočeno (neaktivní okno)")
                           # Plánovaný start se přeskočí a do new_planned_starts se nepřidá
                   else:
                       new_planned_starts.append(start)

               # NOVÝ KÓD - Kontrola pro EXTREME domy, zda jsme minutu po konci neaktivního okna
               if current_minute == 1 and house_id in extreme_house_ids:
                   windows = weekend_hours if is_weekend else weekday_hours
                   if windows:
                       changed = False
                       for i, window in enumerate(windows):
                           # Kontrola, zda jsme minutu po konci okna a zda je okno neaktivní
                           end_hour = window.get('end', 0)
                           is_window_active = window.get('is_active', True)
                           
                           if not is_window_active and current_hour == end_hour:
                               # Aktivujeme okno
                               windows[i]['is_active'] = True
                               changed = True
                               logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (ON_DEMAND): Okno {window['start']}:00-{window['end']}:00 znovu aktivováno v {current_hour}:01")
                       
                       if changed:
                           # Uložíme změněná data zpět do databáze
                           update_field = 'weekend_hours' if is_weekend else 'weekday_hours'
                           cur.execute(f"""
                               UPDATE api_appliance 
                               SET {update_field} = %s::jsonb
                               WHERE id = %s
                           """, [json.dumps(windows), appliance_id])

               # Plánování na další hodinu (v 59. minutě)
               if current_minute == 59:
                   next_hour = (current_hour + 1) % 24
                   windows = weekend_hours if is_weekend else weekday_hours
                   
                   if windows:
                       for i, window in enumerate(windows):
                           if window['start'] == next_hour:
                               # EXTREME logika pro kontrolu is_active u ON_DEMAND
                               is_extreme_house = house_id in extreme_house_ids
                               is_window_active = window.get('is_active', True)
                               
                               if is_extreme_house and not is_window_active:
                                   # Pro neaktivní okno pouze přeskočíme plánování
                                   logger.info(f"EXTREME dům {house_id}, spotřebič {appliance_id} (ON_DEMAND): Přeskakuji plánování pro neaktivní okno {window['start']}:00-{window['end']}:00")
                                   continue  # Přeskočíme plánování pro toto okno
                               
                               # Původní logika pro plánování
                               for _ in range(window.get('uses', 1)):
                                   if random.random() < window['probability']:
                                       start_minutes = window['start'] * 60
                                       end_minutes = window['end'] * 60
                                       if end_minutes < start_minutes:
                                           end_minutes += 24 * 60

                                       random_minute = random.randint(start_minutes, end_minutes)
                                       target_hour = (random_minute // 60) % 24
                                       target_minute = random_minute % 60
                                       
                                       planned_start = current_time.replace(
                                           hour=target_hour,
                                           minute=target_minute
                                       )
                                       new_planned_starts.append(planned_start.strftime('%Y-%m-%d %H:%M:%S'))
                                       logger.debug(f"Spotřebič {appliance_id} (ON_DEMAND): Naplánován start na {planned_start}")
                               break

               cur.execute("""
                   UPDATE api_appliance 
                   SET remaining_minutes_list = %s::jsonb,
                       planned_starts = %s::jsonb
                   WHERE id = %s
               """, [json.dumps(new_remaining_minutes), json.dumps(new_planned_starts), appliance_id])

           else:
               minute_consumption = 0
               logger.debug(f"Spotřebič {appliance_id}: přeskakuji (typ {app_type})")
               
           # Přidáme spotřebič do seznamu a přičteme jeho spotřebu k celkové
           houses[house_id]['appliances'].append({
               "appliance_id": appliance_id,
               "consumption_w": minute_consumption
           })
           houses[house_id]['total_wh'] += minute_consumption  # Wm = Wh/60
       
       # Pokud dům 9 je mezi aktivními, zkopírujeme jeho data i pro další speciální domy
       if 9 in houses and len(special_house_ids) > 1:
           house9_data = houses[9]
           
           # Pro každý další speciální dům (kromě domu 9), který je aktivní
           for house_id in [h for h in special_house_ids if h != 9]:
               # Zkopírujeme data domu 9 do tohoto domu
               houses[house_id] = {
                   'appliances': house9_data['appliances'].copy(),
                   'total_wh': house9_data['total_wh']
               }
               logger.info(f"Data domu 9 zkopírována do domu {house_id}")
       
       # Pro každý dům uložíme data a odečteme z baterie
       for house_id, house_data in houses.items():
           if house_data['appliances']:
               # Načteme aktuální stav baterie a účinnost vybíjení
               cur.execute("""
                   SELECT current_battery_level, discharging_efficiency
                   FROM api_house
                   WHERE id = %s
               """, [house_id])
               battery_level, efficiency = cur.fetchone()
               
               # Převedeme spotřebu na kWh a aplikujeme účinnost
               needed_kwh = (house_data['total_wh'] / 1000) / (efficiency / 100)
               
               # Vybijeme baterii
               new_level = battery_level - needed_kwh
               
               # Aktualizujeme stav baterie
               cur.execute("""
                   UPDATE api_house 
                   SET current_battery_level = %s
                   WHERE id = %s
               """, [new_level, house_id])
               
               logger.info(f"Dům {house_id}: spotřeba {house_data['total_wh']:.2f}Wh, baterie {battery_level:.2f}kWh -> {new_level:.2f}kWh")
               
               # Uložíme data o spotřebě
               cur.execute("""
                   INSERT INTO api_consumptiondata (house_id, date, time, appliance_consumption)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (house_id, date, time) 
                   DO UPDATE SET appliance_consumption = EXCLUDED.appliance_consumption
               """, (house_id, current_date, current_time_str, json.dumps(house_data['appliances'])))
       
       conn.commit()
       logger.info(f"HOTOVO! SIMULOVÁNO {len(houses)} DOMŮ V ČASE {current_date} {current_time_str}")
       
   except Exception as e:
       logger.error(f"Chyba při simulaci: {str(e)}")
       if 'conn' in locals():
           conn.rollback()
   finally:
       if 'cur' in locals():
           cur.close()
       if 'conn' in locals():
           conn.close()

if __name__ == "__main__":
   simulate_minute_consumption()