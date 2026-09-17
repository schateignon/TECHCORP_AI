import os
import json
import socket
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TECHCORP MCP Server", host="0.0.0.0", port=8001)

DB_HOST = os.getenv("DB_HOST", "192.168.56.20")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://192.168.56.10:8000")

def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=os.getenv("DB_NAME", "techcorp"),
        user=os.getenv("DB_USER", "techapp"),
        password=os.getenv("DB_PASSWORD", "Secret123!"),
        cursor_factory=RealDictCursor
    )

@mcp.tool()
def get_server_info(hostname: str) -> dict:
    """Récupère la fiche d'informations complète d'un serveur dans la BDD PostgreSQL."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM servers WHERE UPPER(hostname) = UPPER(%s);", (hostname,))
            server = cur.fetchone()
            if not server:
                return {"error": f"Serveur {hostname} introuvable."}
            return dict(server)
    finally:
        conn.close()

@mcp.tool()
def list_open_tickets(priority: str = None, hostname: str = None) -> list[dict]:
    """Interroge l'API FastAPI pour lister les tickets ouverts (filtrables par priorité ou hostname)."""
    params = {}
    if priority:
        params["priority"] = priority
    if hostname:
        params["hostname"] = hostname

    resp = requests.get(f"{FASTAPI_URL}/tickets/open", params=params)
    return resp.json()

@mcp.tool()
def check_server_availability(hostname: str, port: int = None) -> dict:
    """Effectue un test de disponibilité réseau (HTTP/TCP) vers le serveur cible."""
    conn = get_db()
    with conn.cursor() as cur:
        # Récupère l'IP et le port associé au serveur en BDD (défaut à 80 si port non défini)
        cur.execute(
            "SELECT ip_address, COALESCE(port, 80) AS default_port FROM servers WHERE UPPER(hostname) = UPPER(%s);",
            (hostname,)
        )
        srv = cur.fetchone()
    conn.close()

    if not srv:
        return {"status": "UNKNOWN", "details": f"Serveur '{hostname}' inconnu dans l'inventaire BDD."}

    ip = str(srv["ip_address"])
    # Utilise le port spécifié lors de l'appel de l'outil, sinon le port enregistré en BDD
    target_port = port if port is not None else srv["default_port"]

    # 1. Test HTTP pour les ports web standards / applicatifs
    if target_port in (80, 443, 8000, 8001, 8080):
        protocol = "https" if target_port == 443 else "http"
        url = f"{protocol}://{ip}:{target_port}"
        
        try:
            resp = requests.head(url, timeout=2.5, allow_redirects=True)
            return {
                "status": "UP",
                "hostname": hostname,
                "ip": ip,
                "port": target_port,
                "http_status": resp.status_code
            }
        except requests.RequestException:
            try:
                resp = requests.get(url, timeout=2.5, stream=True)
                return {
                    "status": "UP",
                    "hostname": hostname,
                    "ip": ip,
                    "port": target_port,
                    "http_status": resp.status_code
                }
            except requests.RequestException:
                pass  # En cas d'échec HTTP, tenter le socket TCP ci-dessous

    # 2. Test Socket TCP (Fallback)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.5)
            res = sock.connect_ex((ip, target_port))
            return {
                "status": "UP" if res == 0 else "SERVICE DOWN",
                "hostname": hostname,
                "ip": ip,
                "port": target_port,
                "socket_code": res
            }
    except Exception as e:
        return {"status": "DOWN", "hostname": hostname, "ip": ip, "port": target_port, "error": str(e)}

@mcp.tool()
def get_recent_events(hostname: str, limit: int = 5) -> list[dict]:
    """Récupère les événements récents liés à un serveur depuis la base de données PostgreSQL."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.* 
                FROM events e
                JOIN servers s ON s.id = e.server_id
                WHERE UPPER(s.hostname) = UPPER(%s)
                ORDER BY e.created_at DESC
                LIMIT %s;
                """,
                (hostname, limit)
            )
            events = cur.fetchall()
            return [dict(event) for event in events]
    finally:
        conn.close()

@mcp.tool()
def get_last_service_check(hostname: str) -> dict:
    """Récupère la dernière mesure historique de contrôle de service pour un serveur dans PostgreSQL."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.* 
                FROM service_checks sc
                JOIN servers s ON s.id = sc.server_id
                WHERE UPPER(s.hostname) = UPPER(%s)
                ORDER BY sc.checked_at DESC
                LIMIT 1;
                """,
                (hostname,)
            )
            check = cur.fetchone()
            if not check:
                return {"message": f"Aucun historique de contrôle trouvé pour {hostname}."}
            return dict(check)
    finally:
        conn.close()

@mcp.tool()
def create_ticket(hostname: str, priority: str, title: str = None, confirm: bool = False) -> dict:
    """Créer un ticket d'incident via l'API FastAPI après validation (confirm=True)."""
    
    # 1. Sécurité HITL : Si la confirmation n'est pas reçue, on bloque l'exécution
    if not confirm:
        return {
            "status": "WAITING_FOR_CONFIRMATION",
            "message": f"Création du ticket pour '{hostname}' en attente de confirmation humaine."
        }

    # 2. Gestion d'un titre par défaut si le LLM ne l'a pas généré
    if not title:
        title = f"Incident détecté sur le serveur {hostname}"

    # 3. Payload conforme au modèle Pydantic TicketCreate (title, hostname, priority)
    payload = {
        "title": title,
        "hostname": hostname,
        "priority": priority.upper()
    }

    # 4. Envoi de la requête vers l'API FastAPI (sur SRV-APP-01)
    try:
        resp = requests.post(f"{FASTAPI_URL}/tickets", json=payload, timeout=5.0)
        resp.raise_for_status()
        return resp.json()  # Renvoie le ticket créé avec son ID
    except requests.RequestException as e:
        return {"error": f"Échec d'appel à l'API FastAPI : {str(e)}"}
    
@mcp.resource("procedure://escalade")
def get_escalation_procedure() -> str:
    """Charge le document d'exploitation interne depuis le dossier procedures/."""
    with open("procedures/procedures_exploitation.txt", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    mcp.run(transport="sse")