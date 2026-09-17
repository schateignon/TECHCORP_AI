from mcp.server import MCPServer
import requests


# Création du serveur MCP
mcp = MCPServer("TECHCORP MCP Server")


# Adresse de notre API FastAPI
TICKETING_API = "http://127.0.0.1:8000"


# ------------------------------------------------
# TOOL 1 : récupérer les tickets ouverts
# ------------------------------------------------

@mcp.tool()
def list_open_tickets() -> list[dict]:
    """
    Liste les tickets ouverts depuis l'API REST TECHCORP.
    """

    response = requests.get(
        f"{TICKETING_API}/status/open",
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ------------------------------------------------
# TOOL 2 : récupérer tous les tickets
# ------------------------------------------------

@mcp.tool()
def list_all_tickets() -> list[dict]:
    """
    Retourne tous les tickets TECHCORP.
    """

    response = requests.get(
        f"{TICKETING_API}/tickets",
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ------------------------------------------------
# TOOL 3 : créer un ticket
# ------------------------------------------------

@mcp.tool()
def create_ticket(
    title: str,
    server: str,
    priority: str
) -> dict:
    """
    Crée un ticket dans l'API TECHCORP.
    """

    ticket = {
        "title": title,
        "server": server,
        "priority": priority
    }

    response = requests.post(
        f"{TICKETING_API}/tickets",
        json=ticket,
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ------------------------------------------------
# DÉMARRAGE DU SERVEUR MCP
# ------------------------------------------------

if __name__ == "__main__":
    mcp.run()