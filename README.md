# 🤖 TECHCORP AI Ops Assistant

Assistant IA d'exploitation SI connecté au SI TECHCORP via Model Context Protocol (MCP), API FastAPI et PostgreSQL.

## 📐 Architecture Réseau

- **SRV-APP-01 (`192.168.56.10`)** : API REST FastAPI (port 8000) & Serveur MCP SSE (port 8001)
- **SRV-DB-01 (`192.168.56.20`)** : Base de données PostgreSQL (port 5432)
- **SRV-WEB-01 (`192.168.56.30`)** : Serveur cible Nginx / SSH (ports 80 / 22)
- **Machine Locale** : Interface Streamlit (`app/client_ui.py`) & LLM Ollama (`qwen2.5`)

## 🚀 Guide de Démarrage

### Ordre d'Exécution Global du TP

# 1. Cloner et préparer l'environnement Python local
python -m venv .env
.\.env\Scripts\activate
pip install -r requirements.txt

# 2. Monter l'infrastructure conteneurisée
docker-compose up --build -d

# 3. Charger le schéma de base de données de test si nécessaire
psql -h 192.168.56.20 -U techapp -d techcorp

# 4. Lancer l'ETL et afficher l'audit
python etl/clean_and_load.py
python etl/audit_report.py

# 5. Lancer l'application IA
ollama serve
streamlit run app/client_ui.py