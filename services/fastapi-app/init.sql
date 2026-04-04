-- NOC Lab — incidents table seed
-- Runs once on first postgres container start

CREATE TABLE IF NOT EXISTS incidents (
    id          SERIAL PRIMARY KEY,
    title       TEXT        NOT NULL,
    severity    TEXT        NOT NULL CHECK (severity IN ('P1', 'P2', 'P3')),
    status      TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'closed')),
    service     TEXT,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

INSERT INTO incidents (title, severity, status, service, description) VALUES
    ('FastAPI service down',        'P1', 'closed',        'fastapi-app',    'Container stopped unexpectedly, restarted via docker compose'),
    ('High CPU utilization',        'P2', 'closed',        'host',           'stress-ng test consuming 95% CPU for 3 minutes'),
    ('Disk space critical',         'P1', 'closed',        'host',           '/tmp filled with test data, cleared manually'),
    ('Database connection timeout', 'P2', 'closed',        'postgres',       'PostgreSQL container OOM killed, restarted'),
    ('Prometheus scrape failure',   'P2', 'closed',        'prometheus',     'Target unreachable due to network misconfiguration'),
    ('Grafana alert storm',         'P2', 'closed',        'grafana',        'Flapping alert due to missing pending period'),
    ('Zabbix agent lost',           'P2', 'resolved',      'zabbix-agent',   'Agent container restarted after host kernel update'),
    ('AlertManager email failure',  'P3', 'resolved',      'alertmanager',   'Gmail App Password expired, rotated'),
    ('Webhook bridge timeout',      'P3', 'closed',        'webhook-bridge', 'Jira API rate limit hit during test, backoff added'),
    ('Node Exporter crash',         'P2', 'closed',        'node-exporter',  'Binary updated, service restarted')
ON CONFLICT DO NOTHING;
