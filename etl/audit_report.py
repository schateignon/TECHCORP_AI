import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def print_audit():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "192.168.56.20"),
        database=os.getenv("DB_NAME", "techcorp"),
        user=os.getenv("DB_USER", "techapp"),
        password=os.getenv("DB_PASSWORD", "Secret123!")
    )
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM ingestion_audit ORDER BY processed_at DESC;")
        logs = cur.fetchall()
        print("\n=== HISTORIQUE DE L'AUDIT D'INGESTION ===")
        for log in logs:
            print(f"ID: {log[0]} | Fichier: {log[1]} | Acceptés: {log[2]} | Rejetés: {log[3]} | Date: {log[4]}")
    conn.close()

if __name__ == "__main__":
    print_audit()