import os
import time
import logging
from typing import Generator
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

# Configuration des logs pour la contrainte de journalisation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_logger")

app = FastAPI(title="TECHCORP Ticketing API")

# --- CONTRAINTE : JOURNALISATION DES REQUÊTES ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(
        f"Méthode: {request.method} | Path: {request.url.path} | "
        f"Statut: {response.status_code} | Temps: {process_time:.2f}ms"
    )
    return response

# Generator de connexion BDD avec try/finally
def get_db() -> Generator:
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "192.168.56.20"),
            database=os.getenv("DB_NAME", "bdd"), 
            user=os.getenv("DB_USER", "user"),            
            password=os.getenv("DB_PASSWORD", "mot de passe"),
            cursor_factory=RealDictCursor
        )
        yield conn
    except Exception as e:
        logger.error(f"Erreur de connexion BDD : {e}")
        raise HTTPException(status_code=500, detail="Erreur interne de base de données")
    finally:
        if conn:
            conn.close()

class TicketCreate(BaseModel):
    title: str
    hostname: str
    priority: str

@app.get("/health")
def health():
    return {"status": "ok", "host": "SRV-APP-01 (192.168.56.10)"}

@app.get("/tickets")
def get_all_tickets(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets ORDER BY id DESC;")
        return cur.fetchall()

@app.get("/tickets/open")
def get_open_tickets(priority: str = None, hostname: str = None, db=Depends(get_db)):
    query = "SELECT * FROM tickets WHERE status = 'OPEN'"
    params = []
    
    if priority:
        query += " AND priority = %s"
        params.append(priority)
    if hostname:
        query += " AND UPPER(hostname) = UPPER(%s)"
        params.append(hostname)
        
    with db.cursor() as cur:
        cur.execute(query, tuple(params))
        return cur.fetchall()

@app.get("/tickets/{id}")
def get_ticket_by_id(id: int, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE id = %s;", (id,))
        ticket = cur.fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket #{id} non trouvé")
        return ticket

@app.get("/servers/{hostname}/tickets")
def get_tickets_by_server(hostname: str, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE UPPER(hostname) = UPPER(%s);", (hostname,))
        return cur.fetchall()

@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketCreate, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO tickets (title, hostname, priority, status)
            VALUES (%s, %s, %s, 'OPEN') RETURNING *;
        """, (ticket.title, ticket.hostname, ticket.priority.upper()))
        created = cur.fetchone()
    
    db.commit()
    logger.info(f"Nouveau ticket créé ID #{created['id']} pour {ticket.hostname}")
    return created