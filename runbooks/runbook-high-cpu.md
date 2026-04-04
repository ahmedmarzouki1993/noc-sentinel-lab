# Runbook: High CPU

## 1. Overview

Host CPU utilization has exceeded 80% for more than 3 minutes.
Caused by runaway processes, CPU-intensive workloads, or container resource leaks.
Grafana alert fires as P2 Warning. Monitor closely — can escalate to P1 if service degradation occurs.

---

## 2. Severity & SLA

| Attribute | Value |
|---|---|
| Classification | P2 — Warning |
| Detect SLA | < 5 minutes |
| Resolve SLA | < 60 minutes |
| Alert name | `Host CPU high` |
| Escalation threshold | CPU > 95% OR service degradation detected |

---

## 3. Prerequisites

- SSH access to the VM: `ssh azureuser@20.74.250.179`
- Access to Grafana CPU panel: `http://20.74.250.179:3000/d/noc-main`
- Docker CLI access on VM

---

## 4. Detection signals

- **Grafana alert:** `Host CPU high` → FIRING (orange/yellow)
- **Prometheus query:** `(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[2m]))) * 100 > 80`
- **Grafana dashboard:** CPU usage % panel spikes above 80%

---

## 5. Initial triage (first 2 minutes)

```bash
ssh azureuser@20.74.250.179

# 1. Confirm CPU spike is real
top -bn1 | head -15

# 2. Identify which container is consuming CPU
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# 3. Check if FastAPI health is still OK (service degradation check)
curl -sf http://localhost:8000/health && echo "APP HEALTHY" || echo "APP DEGRADED"
```

---

## 6. Investigation commands

```bash
ssh azureuser@20.74.250.179

# Host-level: top CPU processes
ps aux --sort=-%cpu | head -15

# Container-level: live stats
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}"

# Identify process inside the offending container (replace NAME)
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app ps aux --sort=-%cpu

# Check if stress-ng is running (simulation artifact)
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app pgrep -a stress-ng

# Check recent CPU history in Prometheus (last 10 min)
curl -s 'http://localhost:9090/api/v1/query_range?query=(1-avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))*100&start=$(date -d "10 minutes ago" +%s)&end=$(date +%s)&step=30' \
  | python3 -m json.tool | grep '"v"' | tail -10
```

**Distinguishing host vs container CPU:**
- `docker stats` shows per-container CPU — if one container is at 200%+, it's a container issue
- `top` shows host processes — if `dockerd` or kernel threads are high, it's a host issue

---

## 7. Resolution steps

### A — Simulation artifact (stress-ng running)
```bash
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app pkill stress-ng
```

### B — Runaway application process
```bash
# Get PID inside container
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app ps aux --sort=-%cpu | head -5
# Kill the process (replace PID)
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app kill -9 <PID>
```

### C — Container resource leak — restart the container
```bash
cd ~/noc-sentinel-lab
docker compose restart fastapi-app
```

### D — Sustained high CPU with no clear cause — restart full stack
```bash
cd ~/noc-sentinel-lab
docker compose restart
```

---

## 8. Verification

```bash
# CPU should return below 20% idle threshold
top -bn1 | grep "Cpu(s)"
# Expected: high %id (idle) value, e.g. "Cpu(s): 5.0us, 2.0sy, 0.0ni, 90.0id"

# Docker stats should show normal CPU
docker stats --no-stream
```

Wait 3 minutes — Grafana `Host CPU high` alert auto-resolves.

---

## 9. Escalation criteria

Escalate to P1 if:
- CPU stays above 95% for more than 10 minutes
- FastAPI health check starts returning 503
- Cannot identify or kill the offending process
- VM becomes unresponsive over SSH

---

## 10. Post-incident actions

1. Document in Jira ticket: root cause, process name, resolution
2. If recurring: add CPU limit to the offending container in `docker-compose.yml`
   ```yaml
   deploy:
     resources:
       limits:
         cpus: "1.5"
   ```
3. Close Jira ticket

---

## 11. Revision history

| Date | Author | Change |
|---|---|---|
| 2026-04-05 | Ahmed Marzouki | Initial version — tested against live NOC lab |
