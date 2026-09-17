import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="TECHCORP Ticketing API")

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "192.168.56.20"),
        database=os.getenv("DB_NAME", "techcorp"),
        user=os.getenv("DB_USER", "techapp"),
        password=os.getenv("DB_PASSWORD", "Secret123!"),
        cursor_factory=RealDictCursor
    )

class TicketCreate(BaseModel):
    title: str
    hostname: str
    priority: str

@app.get("/health")
def health():
    return {"status": "ok", "host": "SRV-APP-01 (192.168.56.10)"}

@app.get("/tickets/open")
def list_open_tickets(priority: str = None):
    conn = get_db()
    with conn.cursor() as cur:
        if priority:
            cur.execute("SELECT * FROM tickets WHERE status='OPEN' AND UPPER(priority)=UPPER(%s);", (priority,))
        else:
            cur.execute("SELECT * FROM tickets WHERE status='OPEN';")
        tickets = cur.fetchall()
    conn.close()
    return tickets

@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketCreate):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tickets (title, hostname, priority, status)
            VALUES (%s, %s, %s, 'OPEN') RETURNING *;
        """, (ticket.title, ticket.hostname, ticket.priority.upper()))
        created = cur.fetchone()
    conn.commit()
    conn.close()
    return created