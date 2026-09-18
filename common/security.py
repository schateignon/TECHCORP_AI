import hmac
import os
import re

HOSTNAME = re.compile(r"^SRV-[A-Z0-9]+(?:-[A-Z0-9]+)*$")

def hostname(value: str) -> str:
    value = value.strip().upper()
    if len(value) > 50 or not HOSTNAME.fullmatch(value):
        raise ValueError("Hostname TECHCORP invalide.")
    return value

def valid_token(header: str, variable: str) -> bool:
    expected = os.getenv(variable, "")
    return bool(expected) and hmac.compare_digest(header, f"Bearer {expected}")

def redact(value):
    if isinstance(value, dict):
        return {k: "[MASQUÉ]" if any(s in k.lower() for s in
                ("password", "token", "secret", "private_key", "api_key", "authorization"))
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for key, secret in os.environ.items():
            if secret and len(secret) >= 4 and any(s in key.upper() for s in ("PASSWORD", "TOKEN", "SECRET")):
                value = value.replace(secret, "[MASQUÉ]")
        return re.sub(r"(?i)(password|mot de passe|token|secret)\s*[:=]\s*[^\s,;]+",
                      r"\1=[MASQUÉ]", value)
    return value
