#!/bin/bash
# Scenario 3 — P1 Critical: Disk space critical
# Fills /tmp inside the fastapi-app container with a large file.
# Expected: disk % drops, Grafana "Host disk critical" alert fires within 2m.
# NOTE: Alert fires on host / mount, not container. Adjust size if VM disk is large.

set -e
cd "$(dirname "$0")/.."

SIZE_MB=${1:-4000}  # default 4 GB — adjust for your VM disk size

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Writing ${SIZE_MB}MB file to /tmp/bigfile..."
docker compose exec -T fastapi-app bash -c "dd if=/dev/zero of=/tmp/bigfile bs=1M count=${SIZE_MB} status=progress"

echo "[$(date -u +%Y-%m-%dT%H:%M:%S)] [SIMULATE] Done. Monitor:"
echo "  - Grafana:    http://localhost:3000  (disk panel + alert within 2 min)"
echo "  - df -h  (on VM host)"
echo ""
echo "  To resolve: bash scripts/resolve-all.sh"
