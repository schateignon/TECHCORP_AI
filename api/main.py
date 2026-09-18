import logging
import time
from typing import Literal
import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from common.db import database
from common.security import hostname, valid_token

logger = logging.getLogger("techcorp.api")
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="TECHCORP Ticketing API", version="2.0")
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info("method=%s endpoint=%s status=%s duration_ms=%.2f",
                    request.method, request.url.path, status, (time.monotonic()-start)*1000)

def authorize(authorization: str = Header(default="")):
    if not valid_token(authorization, "API_TOKEN"):
        raise HTTPException(401, "Authentification requise")

def get_db():
    try:
        with database("api") as conn:
            yield conn
    except psycopg2.Error:
        logger.error("Opération PostgreSQL indisponible")
        raise HTTPException(503, "Base de données indisponible")

class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    hostname: str
    priority: Priority
    description: str = Field(default="", max_length=4000)

    @field_validator("hostname")
    @classmethod
    def normalize_host(cls, value):
        return hostname(value)

    @field_validator("title")
    @classmethod
    def nonempty_title(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Titre trop court")
        return value.strip()

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

@app.get("/health")
def health():
    return {"status": "ok", "component": "ticketing_api", "scope": "process"}

@app.get("/tickets", dependencies=[Depends(authorize)])
def get_all_tickets(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 200")
        return cur.fetchall()

@app.get("/tickets/open", dependencies=[Depends(authorize)])
def get_open_tickets(priority: Priority | None = None, hostname: str | None = None, db=Depends(get_db)):
    query = "SELECT * FROM tickets WHERE status IN ('OPEN','IN_PROGRESS')"
    params = []
    if priority:
        query += " AND priority = %s"
        params.append(priority)
    if hostname:
        query += " AND hostname = %s"
        params.append(hostname.strip().upper())
    with db.cursor() as cur:
        cur.execute(query + " ORDER BY created_at DESC, id DESC LIMIT 200", params)
        return cur.fetchall()

@app.get("/tickets/{id}", dependencies=[Depends(authorize)])
def get_ticket_by_id(id: int, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE id = %s", (id,))
        ticket = cur.fetchone()
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")
    return ticket

@app.get("/servers/{hostname}/tickets", dependencies=[Depends(authorize)])
def get_tickets_by_server(hostname: str, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM tickets WHERE hostname=%s ORDER BY id DESC LIMIT 200",
                    (hostname.strip().upper(),))
        return cur.fetchall()

@app.post("/tickets", status_code=201, dependencies=[Depends(authorize)])
def create_ticket(ticket: TicketCreate, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("""INSERT INTO tickets(title, hostname, priority, status, description)
                    VALUES (%s,%s,%s,'OPEN',%s) RETURNING *""",
                    (ticket.title, ticket.hostname, ticket.priority, ticket.description))
        created = cur.fetchone()
    db.commit()
    logger.info("ticket_created id=%s hostname=%s", created["id"], ticket.hostname)
    return created
