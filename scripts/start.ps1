$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if (-not (Test-Path ".venv/Scripts/python.exe")) { throw "Créer .venv et installer requirements.txt (voir README)." }
    if (-not (Test-Path ".env")) {
        & ./.venv/Scripts/python.exe scripts/setup_env.py
        if ($LASTEXITCODE -ne 0) { throw "Configuration échouée." }
    }
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "Démarrer Docker Desktop et vérifier les messages ci-dessus." }
    & ./.venv/Scripts/python.exe -m streamlit run app/client_ui.py --server.address 127.0.0.1
} finally { Pop-Location }
