"""Import traçable : aucune modification des fichiers sources."""
import argparse
import csv
import ipaddress
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
import psycopg2
from psycopg2.extras import Json
from common.db import database
from common.security import hostname, redact

PRIORITIES = {"CRITIQUE":"CRITICAL", "CRITICAL":"CRITICAL", "HAUT":"HIGH", "HIGH":"HIGH",
              "MOYEN":"MEDIUM", "MEDIUM":"MEDIUM", "BAS":"LOW", "LOW":"LOW"}
STATUSES = {"OPEN":"OPEN", "OUVERT":"OPEN", "NEW":"OPEN", "IN_PROGRESS":"IN_PROGRESS",
            "IN PROGRESS":"IN_PROGRESS", "EN COURS":"IN_PROGRESS", "CLOSED":"CLOSED",
            "FERMÉ":"CLOSED", "FERME":"CLOSED", "RESOLVED":"CLOSED", "RÉSOLU":"CLOSED"}
INVENTORY = {"ACTIVE":"UP", "RUNNING":"UP", "ONLINE":"UP", "UP":"UP",
             "OFFLINE":"DOWN", "STOPPED":"DOWN", "DOWN":"DOWN", "UNKNOWN":"UNKNOWN"}
RESULTS = {"SUCCESS":"SUCCESS", "OK":"SUCCESS", "UP":"SUCCESS", "FAILED":"FAILED",
           "FAIL":"FAILED", "DOWN":"FAILED", "TIMEOUT":"TIMEOUT", "UNKNOWN":"UNKNOWN"}

def parse_date(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Date absente")
    value = value.strip()
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        result = None
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                result = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass
        if result is None:
            raise ValueError("Date invalide")
    # Convention documentée : les dates sans fuseau sont interprétées en UTC.
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)

def port(value):
    result = int(value)
    if not 1 <= result <= 65535:
        raise ValueError("Port hors limites")
    return result

def mapped(value, mapping, field):
    value = str(value).strip().upper()
    if value not in mapping:
        raise ValueError(f"{field} inconnu")
    return mapping[value]

def normalize_server(row):
    if len(row) != 9:
        raise ValueError("Inventaire : 9 colonnes attendues")
    host, ip, role, os_name, service, service_port, status, env, owner = (v.strip() for v in row)
    address = ipaddress.ip_address(ip)
    if address.version != 4 or address.is_loopback or address.is_multicast or address.is_unspecified:
        raise ValueError("Adresse IPv4 de serveur invalide")
    if not role or not service:
        raise ValueError("Rôle ou service absent")
    environment = {"PRODUCTION":"PROD", "DEVELOPMENT":"DEV", "DEVELOPPEMENT":"DEV",
                   "TEST":"TEST", "PROD":"PROD", "DEV":"DEV", "RECETTE":"TEST"}.get(env.upper())
    if not environment:
        raise ValueError("Environnement inconnu")
    return dict(hostname=hostname(host), ip_address=str(address),
                role={"DATABASE":"DB"}.get(role.upper(), role.upper()), os=os_name,
                service_name=service.upper(), port=port(service_port),
                inventory_status=mapped(status, INVENTORY, "Statut"), environment=environment)

def normalize_ticket(row):
    if not isinstance(row, dict):
        raise ValueError("Ticket : objet JSON attendu")
    ticket_id = int(row.get("id", 0))
    title = str(row.get("title") or "").strip()
    if ticket_id < 1 or not 3 <= len(title) <= 255:
        raise ValueError("ID ou titre invalide")
    return dict(id=ticket_id, title=title, hostname=hostname(row.get("hostname", "")),
                priority=mapped(row.get("priority"), PRIORITIES, "Priorité"),
                status=mapped(row.get("status"), STATUSES, "Statut"),
                created_at=parse_date(row.get("created_at")), description=redact(str(row.get("description") or "")))

def read_json_records(path):
    content = path.read_text(encoding="utf-8-sig").strip()
    try:
        value = json.loads(content)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        # Accepte aussi les objets JSON concaténés du sujet ; aucune récupération silencieuse.
        decoder, position, rows = json.JSONDecoder(), 0, []
        while position < len(content):
            if content[position].isspace():
                position += 1
                continue
            value, position = decoder.raw_decode(content, position)
            rows.append(value)
        return rows

def csv_records(path, header_name):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if rows and rows[0] and rows[0][0].strip().lower() == header_name:
        rows = rows[1:]
    return rows

def normalize_check(row):
    if len(row) != 6:
        raise ValueError("Historique : 6 colonnes attendues")
    stamp, host, service_port, result, latency, source = (v.strip() for v in row)
    latency = float(latency) if latency else None
    if latency is not None and (latency < 0 or not __import__("math").isfinite(latency)):
        raise ValueError("Latence invalide")
    return dict(timestamp=parse_date(stamp), hostname=hostname(host), port=port(service_port),
                tcp_result=mapped(result, RESULTS, "Résultat TCP"), latency_ms=latency,
                source=source or "import")

def normalize_event(line):
    # Format ISO ou français, avec espaces ou | ; composant facultatif.
    match = re.fullmatch(
        r"\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?|\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"
        r"[ |]+\[?(INFO|WARN|WARNING|ERROR|CRITICAL)\]?[ |]+(srv-[\w-]+)[ |]+(.+)", line, re.I)
    if not match:
        raise ValueError("Format événement non reconnu")
    stamp, level, host, tail = match.groups()
    if "|" in tail:
        component, message = (s.strip() for s in tail.split("|", 1))
    else:
        component, message = "system", tail.strip()
    return dict(timestamp=parse_date(stamp), level="WARN" if level.upper()=="WARNING" else level.upper(),
                hostname=hostname(host), component=component, message=redact(message))

def correction_count(raw, normalized):
    if isinstance(raw, dict):
        return any(str(raw.get(k, "")).strip() != str(v) for k, v in normalized.items()
                   if k not in ("created_at", "description"))
    if isinstance(raw, list) and len(raw) == 9:
        return any(raw[i] != str(normalized[k]) for i, k in
                   [(0,"hostname"),(1,"ip_address"),(2,"role"),(4,"service_name"),
                    (5,"port"),(6,"inventory_status"),(7,"environment")])
    if isinstance(raw, list) and len(raw) == 6:
        return raw[1] != normalized["hostname"] or raw[3] != normalized["tcp_result"]
    return isinstance(raw, str) and normalized.get("hostname", "") not in raw

def insert_row(cur, table, row):
    keys = list(row)
    # table et colonnes proviennent exclusivement des normaliseurs internes.
    cur.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join(['%s']*len(keys))}) "
                "ON CONFLICT DO NOTHING", list(row.values()))
    return cur.rowcount

def import_file(cur, path, table, normalizer, run_id, label):
    stats = dict(accepted=0, rejected=0, corrected=0, duplicates=0)
    details = []
    try:
        if table == "servers":
            rows = csv_records(path, "hostname")
        elif table == "service_checks":
            rows = csv_records(path, "timestamp")
        elif table == "tickets":
            rows = read_json_records(path)
        else:
            rows = path.read_text(encoding="utf-8-sig").splitlines()
    except (ValueError, OSError) as exc:
        raise ValueError(f"Impossible de lire {path.name} : {type(exc).__name__}") from exc
    for index, raw in enumerate(rows, 1):
        cur.execute("SAVEPOINT ingestion_row")
        try:
            row = normalizer(raw)
            corrected = correction_count(raw, row)
            service = row.pop("service_name", None)
            inserted = insert_row(cur, table, row)
            if table == "servers" and inserted:
                insert_row(cur, "services", dict(hostname=row["hostname"], service_name=service,
                           port=row["port"], expected_state="UP"))
            stats["accepted" if inserted else "duplicates"] += 1
            stats["corrected"] += int(corrected and bool(inserted))
            if not inserted:
                details.append({"record": index, "reason": "Doublon : première valeur valide conservée"})
            elif corrected:
                details.append({"record": index, "reason": "Normalisation appliquée"})
        except (ValueError, TypeError, AttributeError, psycopg2.Error) as exc:
            cur.execute("ROLLBACK TO SAVEPOINT ingestion_row")
            stats["rejected"] += 1
            reason = str(exc) if not isinstance(exc, psycopg2.Error) else "Contrainte SQL ou référence inventaire absente"
            details.append({"record": index, "reason": redact(reason)})
        finally:
            cur.execute("RELEASE SAVEPOINT ingestion_row")
    cur.execute("""INSERT INTO ingestion_audit
        (run_id, source_file, dataset_label, accepted, rejected, corrected, duplicates, details)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (run_id, path.name, label, stats["accepted"], stats["rejected"], stats["corrected"],
         stats["duplicates"], Json(details)))
    return {"file": path.name, **stats}

def run_import(data_dir, label):
    files = [
        ("servers_inventory_raw.csv", "servers", normalize_server),
        ("tickets_raw.json", "tickets", normalize_ticket),
        ("service_checks_raw.csv", "service_checks", normalize_check),
        ("events_raw.log", "events", normalize_event)]
    # Les extraits du sujet ne contiennent que l'inventaire et les tickets.
    # Les historiques et événements sont chargés lorsqu'ils sont fournis.
    for filename, _, _ in files[:2]:
        if not (data_dir / filename).is_file():
            raise ValueError(f"Fichier manquant : {data_dir / filename}")
    skipped_files = [name for name, _, _ in files[2:] if not (data_dir / name).is_file()]
    files = [entry for entry in files if entry[0] not in skipped_files]
    run_id = str(uuid.uuid4())
    with database("etl") as conn, conn.cursor() as cur:
        reports = [import_file(cur, data_dir/name, table, normalizer, run_id, label)
                   for name, table, normalizer in files]
        # Les IDs importés ne doivent pas entrer en collision avec les créations API.
        cur.execute("SELECT setval('tickets_id_seq', GREATEST(COALESCE((SELECT MAX(id) FROM tickets),0), "
                    "(SELECT last_value FROM tickets_id_seq),1), true)")
    return {"run_id": run_id, "dataset_label": label, "sources": reports,
            "skipped_files": skipped_files}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--label", required=True, help="Provenance explicite du jeu importé")
    args = parser.parse_args()
    print(json.dumps(run_import(args.data_dir, args.label), indent=2, ensure_ascii=False))
