import logging
import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger(os.getenv("SERVICE_NAME", "apotek-app"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "apotek"),
    "user": os.getenv("DB_USER", "apotek_user"),
    "password": os.getenv("DB_PASSWORD", "apotek_pass"),
}

SEED_PRODUCTS = [
    ("Paracetamol 500mg", "Pereda demam & nyeri", 5000, 150),
    ("Amoxicillin 500mg", "Antibiotik", 12000, 80),
    ("Vitamin C 1000mg", "Suplemen daya tahan tubuh", 25000, 60),
    ("OBH Combi Batuk", "Obat batuk berdahak", 18000, 45),
    ("Antasida Doen", "Obat maag / asam lambung", 8000, 90),
    ("Betadine 15ml", "Antiseptik luka", 15000, 70),
    ("Masker Medis (50pcs)", "Alat pelindung diri", 35000, 40),
    ("Oralit", "Larutan rehidrasi", 3000, 200),
]

def get_conn():
    return psycopg2.connect(
        cursor_factory=RealDictCursor, connect_timeout=5, **DB_CONFIG
    )

def init_db(retries=10, delay=2):
    last_err = None
    for i in range(retries):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    name          VARCHAR(100) NOT NULL,
                    email         VARCHAR(150) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at    TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id          SERIAL PRIMARY KEY,
                    name        VARCHAR(150) NOT NULL,
                    description VARCHAR(255),
                    price       INTEGER NOT NULL,
                    stock       INTEGER NOT NULL
                );
            """)
            cur.execute("SELECT COUNT(*) AS c FROM products;")
            if cur.fetchone()["c"] == 0:
                cur.executemany(
                    "INSERT INTO products (name, description, price, stock) "
                    "VALUES (%s, %s, %s, %s);",
                    SEED_PRODUCTS,
                )
                log.info("Seeded products table with initial medicines")
            conn.commit()
            cur.close()
            conn.close()
            log.info("Database initialized successfully")
            return True
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "authentication" in msg or "password" in msg:
                log.error("Database initialization failed: database authentication failed")
                return False
            log.warning(f"Database not ready yet (retry {i + 1}/{retries}): {e}")
            time.sleep(delay)
    log.error("Database initialization failed: cannot connect to database")
    return False
