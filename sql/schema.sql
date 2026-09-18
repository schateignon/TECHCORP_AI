-- Initialisation d'un volume neuf ; aucune suppression de données.
CREATE TABLE IF NOT EXISTS servers (
 hostname VARCHAR(50) PRIMARY KEY, ip_address INET NOT NULL,
 role VARCHAR(50) NOT NULL, os VARCHAR(100), environment VARCHAR(20) NOT NULL,
 inventory_status VARCHAR(20) NOT NULL CHECK (inventory_status IN ('UP','DOWN','UNKNOWN')),
 port INT NOT NULL CHECK (port BETWEEN 1 AND 65535)
);
CREATE TABLE IF NOT EXISTS services (
 id SERIAL PRIMARY KEY, hostname VARCHAR(50) REFERENCES servers(hostname),
 service_name VARCHAR(50) NOT NULL, port INT NOT NULL CHECK (port BETWEEN 1 AND 65535),
 expected_state VARCHAR(20) NOT NULL DEFAULT 'UP', UNIQUE(hostname, port)
);
CREATE TABLE IF NOT EXISTS tickets (
 id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL CHECK (length(trim(title)) > 0),
 -- Pas de FK : les tickets orphelins sont conservés et signalés.
 hostname VARCHAR(50) NOT NULL,
 priority VARCHAR(20) NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
 status VARCHAR(20) NOT NULL CHECK (status IN ('OPEN','IN_PROGRESS','CLOSED')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, description TEXT
);
CREATE TABLE IF NOT EXISTS service_checks (
 id SERIAL PRIMARY KEY, timestamp TIMESTAMPTZ NOT NULL,
 hostname VARCHAR(50) REFERENCES servers(hostname), port INT NOT NULL CHECK (port BETWEEN 1 AND 65535),
 tcp_result VARCHAR(20) NOT NULL CHECK (tcp_result IN ('SUCCESS','FAILED','TIMEOUT','UNKNOWN')),
 latency_ms FLOAT CHECK (latency_ms >= 0), source VARCHAR(100),
 UNIQUE(timestamp, hostname, port, source)
);
CREATE TABLE IF NOT EXISTS events (
 id SERIAL PRIMARY KEY, timestamp TIMESTAMPTZ NOT NULL,
 level VARCHAR(10) NOT NULL CHECK (level IN ('INFO','WARN','ERROR','CRITICAL')),
 hostname VARCHAR(50) REFERENCES servers(hostname), component VARCHAR(100), message TEXT NOT NULL,
 UNIQUE(timestamp, hostname, component, message)
);
CREATE TABLE IF NOT EXISTS ingestion_audit (
 id SERIAL PRIMARY KEY, run_id UUID NOT NULL, source_file VARCHAR(100) NOT NULL,
 dataset_label TEXT NOT NULL, accepted INT NOT NULL, rejected INT NOT NULL,
 corrected INT NOT NULL, duplicates INT NOT NULL,
 details JSONB NOT NULL DEFAULT '[]', processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS events_host_time ON events(hostname, timestamp DESC);
CREATE INDEX IF NOT EXISTS checks_host_time ON service_checks(hostname, port, timestamp DESC);
