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

        # Pro každý dům vygenerujeme novou variaci
        for house_id, in houses:
            try:
                variation = random.uniform(0.8, 1.2)
                
                # Aktualizujeme dům
                cur.execute("""
                    UPDATE api_house 
                    SET solar_variation = %s
                    WHERE id = %s
                """, (variation, house_id))
                
                logger.info(f"Dům s ID {house_id}: variace pro dnešek = {variation:.2f}")
                
            except Exception as e:
                logger.error(f"Chyba při generování variace pro dům s ID {house_id}: {str(e)}")
                continue

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