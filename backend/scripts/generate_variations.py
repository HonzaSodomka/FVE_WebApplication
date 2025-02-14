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
        logger.info("Starting generation of solar variations")
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
        logger.info(f"Found {len(houses)} active houses")

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
                
                logger.info(f"House {house_id}: new variation = {variation:.2f}")
                
            except Exception as e:
                logger.error(f"Error generating variation for house {house_id}: {str(e)}")
                continue

        conn.commit()
        logger.info("Successfully generated variations for all active houses")

    except Exception as e:
        logger.error(f"Failed to generate variations: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    generate_variations()