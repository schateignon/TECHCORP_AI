import os
from contextlib import contextmanager
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@contextmanager
def database(role="mcp"):
    users = {"api": "tech_api", "mcp": "tech_reader", "etl": "tech_etl"}
    password = os.environ.get(f"{role.upper()}_DB_PASSWORD")
    if not password:
        raise RuntimeError(f"Configuration manquante : {role.upper()}_DB_PASSWORD")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "techcorp"), user=users[role], password=password,
        connect_timeout=3, options="-c statement_timeout=5000", cursor_factory=RealDictCursor)
    try:
        with conn:
            yield conn
    finally:
        conn.close()
