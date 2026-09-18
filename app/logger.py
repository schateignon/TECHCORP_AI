import json
from datetime import datetime, timezone
from common.db import ROOT
from common.security import redact

LOG_DIR = ROOT / "logs"

def audit(request_id, question, tool_name, arguments, source, duration_ms=0,
          status="success", result=None):
    LOG_DIR.mkdir(exist_ok=True)
    entry = redact({
        "timestamp":datetime.now(timezone.utc).isoformat(), "request_id":request_id,
        "user_question":question, "tool_name":tool_name, "tool_arguments":arguments,
        "tool_status":status, "source":source, "duration_ms":round(duration_ms,2),
        "result":result})
    with (LOG_DIR / "app_audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
