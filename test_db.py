import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("DB_CONN")

print(f"Connecting to: {conn_str[:20]}...")
try:
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            print("Successfully connected and executed SELECT 1")
except Exception as e:
    print(f"Connection failed: {e}")
