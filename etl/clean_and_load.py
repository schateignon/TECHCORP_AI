import os
import csv
import json
import psycopg2
import ipaddress
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_NAME = os.getenv("DB_NAME", "db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASSWORD", "Mot-de-passe")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def clean_servers(conn):
    accepted, rejected = 0, 0
    seen_hostnames = set()

    with open("data_raw/servers_inventory_raw.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        with conn.cursor() as cur:
            for row in reader:
                if not row or len(row) < 9:
                    rejected += 1
                    continue
                
                hostname = row[0].strip().upper()
                ip = row[1].strip()
                role = row[2].strip()
                os_sys = row[3].strip()
                env = row[7].strip().upper()
                status = row[6].strip().upper()
                
                # Normalisation du statut
                if status in ["ACTIVE", "RUNNING"]:
                    status = "UP"
                
                # Validation IP
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    rejected += 1
                    continue

                # Deduplication
                if hostname in seen_hostnames or not hostname:
                    rejected += 1
                    continue

                seen_hostnames.add(hostname)
                cur.execute("""
                    INSERT INTO servers (
                        hostname,
                        ip_address,
                        role,
                        os,
                        environment,
                        inventory_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (hostname) DO NOTHING
                """, (hostname, ip, role, os_sys, env, status))

                if cur.rowcount == 1:
                    accepted += 1
                else:
                    rejected += 1


            cur.execute("INSERT INTO ingestion_audit (source_file, accepted, rejected) VALUES (%s, %s, %s)",
                        ("servers_inventory_raw.csv", accepted, rejected))
    conn.commit()
    print(f"Servers -> Acceptés: {accepted}, Rejetés: {rejected}")

def clean_tickets(conn):
    accepted, rejected = 0, 0

    with open("data_raw/tickets_raw.json", "r", encoding="utf-8") as f:
        content = f.read()

        decoder = json.JSONDecoder()
        tickets = []
        position = 0

        while position < len(content):
            # Ignorer espaces et retours à la ligne
            while position < len(content) and content[position].isspace():
                position += 1

            if position >= len(content):
                break

            ticket, end = decoder.raw_decode(content, position)
            tickets.append(ticket)
            position = end


    with conn.cursor() as cur:
        for ticket in tickets:
            ticket_id = ticket.get("id")
            title = ticket.get("title", "").strip()
            hostname = ticket.get("hostname", "").strip().upper()
            priority = ticket.get("priority", "").strip().upper()
            status = ticket.get("status", "").strip().upper()
            created_at = ticket.get("created_at")

            # Validation des champs obligatoires
            if not ticket_id or not title or not hostname or not priority or not status:
                rejected += 1
                continue

            # Normalisation
            if status == "OPEN":
                status = "OPEN"

            # Vérification de la priorité
            allowed_priorities = {"LOW", "MEDIUM", "HIGH", "CRITIQUE", "CRITICAL"}

            if priority not in allowed_priorities:
                rejected += 1
                continue

            cur.execute("""
                INSERT INTO tickets
                    (id, title, hostname, priority, status, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                ticket_id,
                title,
                hostname,
                priority,
                status,
                created_at
            ))

            accepted += 1

        cur.execute("""
            INSERT INTO ingestion_audit
                (source_file, accepted, rejected)
            VALUES
                (%s, %s, %s)
        """, (
            "tickets_raw.json",
            accepted,
            rejected
        ))

    conn.commit()

    print(f"Tickets -> Acceptés: {accepted}, Rejetés: {rejected}")


if __name__ == "__main__":
    connection = get_db_connection()
    clean_servers(connection)
    clean_tickets(connection)   
    connection.close()