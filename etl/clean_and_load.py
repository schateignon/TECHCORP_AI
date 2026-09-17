import os
import csv
import json
import psycopg2
import ipaddress
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "192.168.56.20")
DB_NAME = os.getenv("DB_NAME", "TECHCORP_AI")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "Secret123!")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def parse_date(date_str):
    """Gère le parsing des formats ISO et Français (9.1)."""
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def clean_servers(conn):
    accepted, rejected = 0, 0
    seen_hostnames = set()

    with open("data_raw/servers_inventory_raw.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        with conn.cursor() as cur:
            for row in reader:
                if not row or len(row) < 7:
                    rejected += 1
                    continue
                
                # Strip + Upper sur le hostname (9.1)
                hostname = row[0].strip().upper()
                ip = row[1].strip()
                role = row[2].strip()
                os_sys = row[3].strip()
                env = row[4].strip().upper() if len(row) > 4 else "PROD"
                status_raw = row[6].strip().upper() if len(row) > 6 else "UP"
                
                # Normalisation du statut (9.1)
                status_mapping = {"ACTIVE": "UP", "RUNNING": "UP", "ONLINE": "UP", "OFFLINE": "DOWN", "STOPPED": "DOWN"}
                status = status_mapping.get(status_raw, status_raw)
                
                # Validation IP (9.1)
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    rejected += 1
                    continue

                # Déduplication (9.1)
                if not hostname or hostname in seen_hostnames:
                    rejected += 1
                    continue

                seen_hostnames.add(hostname)
                
                cur.execute("""
                    INSERT INTO servers (hostname, ip_address, role, os, environment, inventory_status, port)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (hostname) DO NOTHING
                """, (hostname, ip, role, os_sys, env, status, 80))
                if cur.rowcount > 0:
                    accepted += 1

            cur.execute(
                "INSERT INTO ingestion_audit (source_file, accepted, rejected) VALUES (%s, %s, %s)",
                ("servers_inventory_raw.csv", accepted, rejected)
            )
    conn.commit()
    print(f"✅ Serveurs -> Acceptés: {accepted}, Rejetés: {rejected}")

def clean_tickets(conn):
    accepted, rejected = 0, 0

    with open("data_raw/tickets_raw.json", "r", encoding="utf-8") as f:
        content = f.read()

    decoder = json.JSONDecoder()
    tickets, position = [], 0

    while position < len(content):
        while position < len(content) and content[position].isspace():
            position += 1
        if position >= len(content):
            break
        try:
            ticket, end = decoder.raw_decode(content, position)
            tickets.append(ticket)
            position = end
        except json.JSONDecodeError:
            position += 1

    # Normalisation de la priorité (9.1)
    priority_map = {
        "CRITIQUE": "CRITICAL",
        "CRITICAL": "CRITICAL",
        "HAUT": "HIGH",
        "HIGH": "HIGH",
        "MOYEN": "MEDIUM",
        "MEDIUM": "MEDIUM",
        "BAS": "LOW",
        "LOW": "LOW"
    }

    with conn.cursor() as cur:
        for ticket in tickets:
            ticket_id = ticket.get("id")
            title = ticket.get("title", "").strip()
            hostname = ticket.get("hostname", "").strip().upper()
            raw_priority = str(ticket.get("priority", "")).strip().upper()
            status = str(ticket.get("status", "")).strip().upper()
            created_at_parsed = parse_date(ticket.get("created_at"))

            # Validation champs obligatoires & priorité
            if not ticket_id or not title or not hostname or raw_priority not in priority_map:
                rejected += 1
                continue

            norm_priority = priority_map[raw_priority]

            cur.execute("""
                INSERT INTO tickets (id, title, hostname, priority, status, created_at)
                VALUES (%s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                ON CONFLICT (id) DO NOTHING
            """, (ticket_id, title, hostname, norm_priority, status, created_at_parsed))

            if cur.rowcount > 0:
                accepted += 1
            else:
                rejected += 1

        cur.execute(
            "INSERT INTO ingestion_audit (source_file, accepted, rejected) VALUES (%s, %s, %s)",
            ("tickets_raw.json", accepted, rejected)
        )
        
    conn.commit()
    print(f"✅ Tickets -> Acceptés: {accepted}, Rejetés: {rejected}")

def generate_indicators_report(conn):
    """Génère les 6 indicateurs demandés à la section 9.2 du sujet."""
    print("\n" + "="*50)
    print("📊 RAPPORT DES INDICATEURS D'INGESTION (9.2)")
    print("="*50)
    
    with conn.cursor() as cur:
        # 1. Total serveurs bruts / uniques
        cur.execute("SELECT SUM(accepted + rejected) FROM ingestion_audit WHERE source_file LIKE '%server%';")
        total_raw = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(DISTINCT hostname) FROM servers;")
        total_unique = cur.fetchone()[0] or 0
        print(f"1. Serveurs bruts : {total_raw} | Uniques en BDD : {total_unique}")

        # 2. Total enregistrements rejetés
        cur.execute("SELECT SUM(rejected) FROM ingestion_audit;")
        total_rejected = cur.fetchone()[0] or 0
        print(f"2. Total enregistrements rejetés (global) : {total_rejected}")

        # 3. Tickets ouverts par priorité
        cur.execute("SELECT priority, COUNT(*) FROM tickets WHERE status = 'OPEN' GROUP BY priority;")
        print("3. Tickets ouverts par priorité :")
        for priority, count in cur.fetchall():
            print(f"   - {priority}: {count}")

        # 4. Tickets associés à un serveur absent de l'inventaire
        cur.execute("""
            SELECT COUNT(*) FROM tickets t 
            LEFT JOIN servers s ON UPPER(t.hostname) = UPPER(s.hostname) 
            WHERE s.hostname IS NULL;
        """)
        orphans = cur.fetchone()[0] or 0
        print(f"4. Tickets associés à un serveur absent de l'inventaire : {orphans}")

        # 5. Contradictions inventaire UP / dernier test TCP FAILED
        cur.execute("""
            SELECT s.hostname, s.inventory_status, c.tcp_result AS last_check 
            FROM servers s
            JOIN service_checks c ON UPPER(s.hostname) = UPPER(c.hostname)
            WHERE s.inventory_status = 'UP' 
            AND UPPER(c.tcp_result) IN ('FAILED', 'DOWN', 'TIMEOUT');
        """)
        contradictions = cur.fetchall()
        print(f"5. Contradictions inventaire UP / dernier check FAILED ({len(contradictions)}) :")
        for host, inv, check in contradictions:
            print(f"   - {host}: Inventaire={inv} | Dernier Test={check}")

        # 6. Top serveurs avec le plus d'événements ERROR
        cur.execute("""
            SELECT hostname, COUNT(*) as err_count 
            FROM events 
            WHERE UPPER(level) IN ('ERROR', 'CRITICAL') 
            GROUP BY hostname 
            ORDER BY err_count DESC LIMIT 3;
        """)
        print("6. Top serveurs avec le plus d'événements ERROR / CRITICAL :")
        for host, count in cur.fetchall():
            print(f"   - {host}: {count} événements")
        for host, count in cur.fetchall():
            print(f"   - {host}: {count} erreurs")
    print("="*50)

if __name__ == "__main__":
    connection = get_db_connection()
    clean_servers(connection)
    clean_tickets(connection)
    generate_indicators_report(connection)
    connection.close()