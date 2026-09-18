def indicators(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT * FROM ingestion_audit WHERE run_id =
                    (SELECT run_id FROM ingestion_audit ORDER BY processed_at DESC,id DESC LIMIT 1)
                    ORDER BY id""")
        audit = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) AS count FROM servers")
        unique = cur.fetchone()["count"]
        cur.execute("SELECT priority, COUNT(*) AS count FROM tickets "
                    "WHERE status IN ('OPEN','IN_PROGRESS') GROUP BY priority ORDER BY priority")
        tickets = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS count FROM tickets t LEFT JOIN servers s USING(hostname) WHERE s.hostname IS NULL")
        orphans = cur.fetchone()["count"]
        cur.execute("""SELECT s.hostname, s.inventory_status, c.port, c.tcp_result, c.timestamp
            FROM servers s JOIN (
              SELECT DISTINCT ON (hostname,port) hostname,port,tcp_result,timestamp
              FROM service_checks ORDER BY hostname,port,timestamp DESC,id DESC
            ) c ON s.hostname=c.hostname AND s.port=c.port
            WHERE s.inventory_status='UP' AND c.tcp_result IN ('FAILED','TIMEOUT')
            ORDER BY s.hostname""")
        contradictions = cur.fetchall()
        cur.execute("SELECT hostname, COUNT(*) AS count FROM events WHERE level='ERROR' "
                    "GROUP BY hostname ORDER BY count DESC,hostname LIMIT 5")
        errors = cur.fetchall()
    return {"dataset_labels": sorted({r["dataset_label"] for r in audit}),
            "raw_servers_last_run": sum(r["accepted"]+r["rejected"]+r["duplicates"]
                                       for r in audit if r["source_file"]=="servers_inventory_raw.csv"),
            "unique_servers": unique, "rejected_last_run": sum(r["rejected"] for r in audit),
            "corrected_last_run": sum(r["corrected"] for r in audit),
            "open_tickets_by_priority": tickets, "orphan_tickets": orphans,
            "inventory_vs_last_check": contradictions, "top_error_servers": errors,
            "ingestion_audit": audit}
