#!/bin/bash
# Resolve all simulated incidents — run after any simulation scenario.
# Restores the stack to a healthy baseline state.

set -e
cd "$(dirname "$0")/.."

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Starting cleanup..."

# Restart fastapi-app if stopped
if ! docker compose ps fastapi-app | grep -q "running"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Starting fastapi-app..."
    docker compose start fastapi-app
fi

# Kill stress-ng if running
if docker compose exec -T fastapi-app pgrep stress-ng > /dev/null 2>&1; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Killing stress-ng..."
    docker compose exec -T fastapi-app pkill stress-ng || true
fi

# Remove bigfile if exists
if docker compose exec -T fastapi-app test -f /tmp/bigfile 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Removing /tmp/bigfile..."
    docker compose exec -T fastapi-app rm -f /tmp/bigfile
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Stack status:"
docker compose ps

echo ""
echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [RESOLVE] Done. Alerts should auto-resolve within 1-3 minutes."
