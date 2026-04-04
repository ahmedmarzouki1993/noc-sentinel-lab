#!/bin/bash
# Scenario 1 — P1 Critical: FastAPI service down
# Stops the fastapi-app container to trigger the "FastAPI service down" alert.
# Expected: Grafana alert fires within 1m, Jira ticket auto-created.

set -e
cd "$(dirname "$0")/.."

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Stopping fastapi-app container..."
docker compose stop fastapi-app

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Done. Monitor:"
echo "  - Grafana:    http://localhost:3000  (alert should fire within 1-2 min)"
echo "  - Prometheus: http://localhost:9090/alerts"
echo "  - Zabbix:     http://localhost:8080  → Monitoring → Problems"
echo ""
echo "  To resolve: bash scripts/resolve-all.sh"
