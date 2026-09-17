import json
import time
import uuid
import logging
from datetime import datetime
from typing import Any, Dict

# Configuration du fichier de logs dédié
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_audit")

# Handler fichier pour conserver les traces
file_handler = logging.FileHandler("app_audit.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)

def sanitize_arguments(args: Dict[str, Any]) -> Dict[str, Any]:
    """11.2 Filtre les données sensibles (mots de passe, tokens, clés SSH)."""
    sensitive_keys = {"password", "token", "secret", "private_key", "api_key", "pwd"}
    clean_args = {}
    for k, v in args.items():
        if any(sk in k.lower() for sk in sensitive_keys):
            clean_args[k] = "***REDACTED***"
        else:
            clean_args[k] = v
    return clean_args

def log_mcp_call(
    user_question: str,
    tool_name: str,
    tool_arguments: Dict[str, Any],
    source: str,
    func_to_execute
) -> Any:
    """Enrobe l'exécution d'un outil pour générer les traces requises (11.1)."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    timestamp = datetime.now().isoformat()
    
    status = "success"
    result = None
    
    try:
        # Exécution de l'outil MCP
        result = func_to_execute()
        return result
    except Exception as e:
        status = "error"
        result = {"error": str(e)}
        raise e
    finally:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # Structure exacte demandée dans la consigne 11.1
        log_entry = {
            "timestamp": timestamp,
            "request_id": request_id,
            "user_question": user_question,
            "tool_name": tool_name,
            "tool_arguments": sanitize_arguments(tool_arguments),
            "tool_status": status,
            "source": source,
            "duration_ms": duration_ms
        }
        
        # Écriture du journal structuré au format JSON
        logger.info(json.dumps(log_entry, ensure_ascii=False))