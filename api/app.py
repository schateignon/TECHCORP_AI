from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="TECHCORP Ticketing API",
    description="API de démonstration pour le cours API, HTTP et MCP",
    version="1.0"
)


# -----------------------------
# DONNÉES SIMULÉES
# -----------------------------

TICKETS = [
    {
        "id": 1,
        "title": "DNS indisponible",
        "server": "SRV-DNS-01",
        "priority": "CRITICAL",
        "status": "OPEN"
    },
    {
        "id": 2,
        "title": "Latence application",
        "server": "SRV-WEB-01",
        "priority": "HIGH",
        "status": "OPEN"
    },
    {
        "id": 3,
        "title": "Mise à jour PostgreSQL",
        "server": "SRV-DB-01",
        "priority": "MEDIUM",
        "status": "CLOSED"
    },
    {
        "id": 4,
        "title": "Certificat à renouveler",
        "server": "SRV-WEB-01",
        "priority": "HIGH",
        "status": "OPEN"
    }
]


# -----------------------------
# MODÈLE DU TICKET
# -----------------------------

class TicketCreate(BaseModel):
    title: str
    server: str
    priority: str


# -----------------------------
# ROUTES API
# -----------------------------

@app.get("/")
def home():
    return {
        "message": "Bienvenue sur l'API TECHCORP"
    }


@app.get("/tickets")
def list_tickets():
    return TICKETS


@app.get("/status/open")
def list_open_tickets():
    return [
        ticket
        for ticket in TICKETS
        if ticket["status"] == "OPEN"
    ]


@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketCreate):

    new_ticket = {
        "id": len(TICKETS) + 1,
        "title": ticket.title,
        "server": ticket.server,
        "priority": ticket.priority,
        "status": "OPEN"
    }

    TICKETS.append(new_ticket)

    return new_ticket