import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL")  # must include sslmode=require

def get_conn():
    if not DB_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DB_URL)