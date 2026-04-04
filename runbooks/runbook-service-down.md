# Runbook: Service Down

## 1. Overview

A critical service (FastAPI app or dependent component) has become unreachable.
Prometheus scrape returns `up=0`. Grafana alert fires within 1 minute.
Jira ticket auto-created as `Incident` with `Highest` priority.

---

## 2. Severity & SLA

| Attribute | Value |
|---|---|
| Classification | P1 — Critical |
| Detect SLA | < 5 minutes |
| Resolve SLA | < 30 minutes |
| Alert name | `FastAPI service down` |
| Runbook owner | NOC Engineer on-call |

---

## 3. Prerequisites

- SSH access to the VM: `ssh azureuser@20.74.250.179`
- Docker CLI access: `docker compose ps` in `~/noc-sentinel-lab`
- Access to Grafana: `http://20.74.250.179:3000`
- Access to Jira: `https://ahmedmarzouki1993.atlassian.net/browse/NOC`

---

## 4. Detection signals

- **Grafana alert:** `FastAPI service down` → FIRING (red)
- **Prometheus:** `up{job="fastapi-app"} == 0`
- **Jira:** New `Incident` ticket auto-created (`NOC-X`)
- **Direct health check fails:**
  ```bash
  curl -sf http://20.74.250.179:8000/health || echo "SERVICE DOWN"
  ```

---

## 5. Initial triage (first 2 minutes)

```bash
# 1. Confirm service is down
curl -sf http://20.74.250.179:8000/health || echo "DOWN CONFIRMED"

# 2. Check container status
ssh azureuser@20.74.250.179 "docker compose -f ~/noc-sentinel-lab/docker-compose.yml ps fastapi-app"

# 3. Assign the Jira ticket to yourself and move to "In Progress"
```

---

## 6. Investigation commands

```bash
ssh azureuser@20.74.250.179

# Container state
docker compose -f ~/noc-sentinel-lab/docker-compose.yml ps

# Last 50 log lines before crash
docker compose -f ~/noc-sentinel-lab/docker-compose.yml logs fastapi-app --tail=50

# Check DB connectivity (common cause of degraded health)
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec postgres \
  psql -U noc_user -d noc_lab -c "SELECT 1"

# Check if OOM killed
dmesg | grep -i "oom\|killed" | tail -10

# Check disk space (full disk can prevent container start)
df -h
```

**Expected outputs:**
- Healthy container: `STATUS: Up X minutes (healthy)`
- Stopped container: `STATUS: Exited (X) X minutes ago`
- DB healthy: returns `?column? = 1`

---

## 7. Resolution steps

### A — Container stopped (most common)
```bash
ssh azureuser@20.74.250.179
cd ~/noc-sentinel-lab
docker compose start fastapi-app
```

### B — Container crashed (exit code non-zero)
```bash
# Check exit code
docker compose ps fastapi-app
# Restart
docker compose restart fastapi-app
# If persists, rebuild
docker compose build fastapi-app && docker compose up -d fastapi-app
```

### C — Database unreachable (health returns 503)
```bash
docker compose restart postgres
docker compose restart fastapi-app
```

### D — Out of disk space
```bash
docker system prune -f
docker compose restart fastapi-app
```

---

## 8. Verification

```bash
# Service responds healthy
curl -s http://20.74.250.179:8000/health | python3 -m json.tool
# Expected: "status": "healthy"

# Prometheus scrape recovers
curl -s 'http://20.74.250.179:9090/api/v1/query?query=up{job="fastapi-app"}' \
  | python3 -m json.tool | grep value
# Expected: "1"
```

Wait 2 minutes — Grafana alert auto-resolves to green. Jira ticket auto-transitions to Resolved.

---

## 9. Escalation criteria

Escalate to senior engineer if:
- Container restarts but crashes again within 5 minutes
- Database is unrecoverable
- Disk is full and cannot be cleared safely
- Downtime exceeds 15 minutes

---

## 10. Post-incident actions

1. Add resolution note to Jira ticket:
   - Root cause
   - Impact duration
   - Fix applied
   - Time to detect / time to resolve
2. Close Jira ticket
3. If recurring: create follow-up task for root cause fix
4. Update this runbook if new resolution path was discovered

---

## 11. Revision history

| Date | Author | Change |
|---|---|---|
| 2026-04-05 | Ahmed Marzouki | Initial version — tested against live NOC lab |
