#!/bin/bash
# Scenario 2 — P2 Warning: High CPU
# Runs stress-ng inside the fastapi-app container for 5 minutes.
# Expected: CPU > 80%, Grafana "Host CPU high" alert fires within 3m.

set -e
cd "$(dirname "$0")/.."

DURATION=${1:-300}  # default 5 minutes

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Installing stress-ng in fastapi-app container..."
docker compose exec -T fastapi-app apt-get update -qq && \
docker compose exec -T fastapi-app apt-get install -y --no-install-recommends stress-ng -q

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Starting CPU stress for ${DURATION}s..."
docker compose exec -d fastapi-app stress-ng --cpu 2 --timeout "${DURATION}s"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] CPU stress running. Monitor:"
echo "  - Grafana:    http://localhost:3000  (CPU panel + alert within 3 min)"
echo "  - docker stats --no-stream"
echo ""
echo "  To stop early: docker compose exec fastapi-app pkill stress-ng"
echo "  To resolve all: bash scripts/resolve-all.sh"
