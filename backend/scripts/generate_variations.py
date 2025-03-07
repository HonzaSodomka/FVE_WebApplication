import psycopg2
import random
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filename='/app/logs/django.log',
    filemode='a'
)

logger = logging.getLogger('api')

def generate_variations():
    try:
        logger.info("ZAČÁTEK SOLAR VARIATIONS PLÁNOVÁNÍ")
        conn = psycopg2.connect(
            dbname="fve_db",
            user="postgres",
            password="heslo",
            host="db"
        )
        cur = conn.cursor()

        # Načteme aktivní domy
        cur.execute("SELECT id FROM api_house WHERE is_active = true")
        houses = cur.fetchall()
        logger.info(f"Plánuji solar variations pro {len(houses)} domů")

        # Speciální domy, které budou používat stejnou variaci jako dům s ID 9
        special_house_ids = [9, 99, 999, 9999, 99999]
        
        # Nejprve vygenerujeme variaci pro dům s ID 9 (pokud existuje)
        variation_for_special_houses = random.uniform(0.8, 1.2)
        special_houses_processed = False
        
        # Pro každý dům vygenerujeme novou variaci
        for house_id, in houses:
            try:
                # Pokud je dům jeden ze speciálních, použijeme pro něj variaci z domu s ID 9
                if house_id in special_house_ids:
                    variation = variation_for_special_houses
                    if house_id == 9:
                        logger.info(f"Dům s ID {house_id}: vygenerována základní variace = {variation:.2f}")
                    else:
                        logger.info(f"Dům s ID {house_id}: použita stejná variace jako dům 9 = {variation:.2f}")
                    special_houses_processed = True
                else:
                    # Pro ostatní domy generujeme unikátní variaci
                    variation = random.uniform(0.8, 1.2)
                    logger.info(f"Dům s ID {house_id}: variace pro dnešek = {variation:.2f}")
                
                # Aktualizujeme dům
                cur.execute("""
                    UPDATE api_house 
                    SET solar_variation = %s
                    WHERE id = %s
                """, (variation, house_id))
                
            except Exception as e:
                logger.error(f"Chyba při generování variace pro dům s ID {house_id}: {str(e)}")
                continue
        
        # Pokud je dům s ID 9 neaktivní, ale existují jiné speciální domy, aktualizujeme je
        if not special_houses_processed:
            logger.info(f"Dům s ID 9 není aktivní, kontroluji další speciální domy")
            # Zkontrolujeme, jestli existují ostatní speciální domy
            cur.execute("SELECT id FROM api_house WHERE id IN (99, 999, 9999, 99999)")
            special_houses = cur.fetchall()
            
            if special_houses:
                logger.info(f"Nalezeno {len(special_houses)} speciálních domů, nastavuji stejnou variaci {variation_for_special_houses:.2f}")
                for house_id, in special_houses:
                    try:
                        cur.execute("""
                            UPDATE api_house 
                            SET solar_variation = %s
                            WHERE id = %s
                        """, (variation_for_special_houses, house_id))
                        logger.info(f"Dům s ID {house_id}: nastavena speciální variace = {variation_for_special_houses:.2f}")
                    except Exception as e:
                        logger.error(f"Chyba při nastavení speciální variace pro dům s ID {house_id}: {str(e)}")

        conn.commit()
        logger.info("GENEROVÁNÍ VARIACÍ PRO VŠECHNY DOMY ÚSPĚŠNĚ DOKONČENO")

    except Exception as e:
        logger.error(f"Chyba při generování variací: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    generate_variations()