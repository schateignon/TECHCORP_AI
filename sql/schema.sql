-- Suppression des tables si elles existent
DROP TABLE IF EXISTS ingestion_audit, events, service_checks, tickets, services, servers CASCADE;

-- 1. Referentiel des serveurs
CREATE TABLE servers (
    hostname VARCHAR(50) PRIMARY KEY,
    ip_address INET NOT NULL,
    role VARCHAR(50) NOT NULL,
    os VARCHAR(50),
    environment VARCHAR(20) NOT NULL,
    inventory_status VARCHAR(20) NOT NULL,
    port INT NOT NULL
);

-- 2. Services exposes
CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(50) REFERENCES servers(hostname) ON DELETE CASCADE,
    service_name VARCHAR(50) NOT NULL,
    port INT NOT NULL,
    expected_state VARCHAR(20) DEFAULT 'UP'
);

-- 3. Incidents et demandes
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    hostname VARCHAR(50),
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 4. Historique des mesures réseau
CREATE TABLE service_checks (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    hostname VARCHAR(50) REFERENCES servers(hostname) ON DELETE CASCADE,
    port INT NOT NULL,
    tcp_result VARCHAR(20) NOT NULL,
    latency_ms FLOAT,
    source VARCHAR(50)
);

-- 5. Evenements et logs
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    level VARCHAR(10) NOT NULL,
    hostname VARCHAR(50) REFERENCES servers(hostname) ON DELETE CASCADE,
    component VARCHAR(50),
    message TEXT NOT NULL
);

-- 6. Ingestion Audit (Traçabilite du nettoyage)
CREATE TABLE ingestion_audit (
    id SERIAL PRIMARY KEY,
    source_file VARCHAR(100) NOT NULL,
    accepted INT NOT NULL,
    rejected INT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);