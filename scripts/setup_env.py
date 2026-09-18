"""Crée une configuration absente sans afficher les secrets."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env existe déjà : conservé. Comparer avec .env.example si nécessaire.")
content = (root / ".env.example").read_text(encoding="utf-8")
for key in ("POSTGRES_PASSWORD", "API_DB_PASSWORD", "MCP_DB_PASSWORD",
            "ETL_DB_PASSWORD", "API_TOKEN", "MCP_TOKEN"):
    content = content.replace(f"{key}=\n", f"{key}={secrets.token_urlsafe(32)}\n")
target.write_text(content, encoding="utf-8")
print("Configuration locale créée dans .env (exclu de Git).")
