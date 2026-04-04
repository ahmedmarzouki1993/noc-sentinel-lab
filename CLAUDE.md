# CLAUDE.md — NOC Sentinel Lab

This file is read by Claude Code at the start of every session.
Do not delete or rename it. Update it when architecture changes.

---

## Project Identity

**Project:** NOC Sentinel Lab  
**Purpose:** Self-contained Network Operations Center training environment  
**Owner:** Ahmed Marzouki — Cloud & DevOps Engineer  
**Goal:** Demonstrate NOC engineering skills: monitoring, alerting, incident management, runbooks  
**Repository:** https://github.com/ahmedmarzouki1993/noc-sentinel-lab  

---

## Architecture Overview

Single Azure VM running all services via Docker Compose.
All inter-service communication uses Docker service names — never `localhost` inside compose configs.

```
VM public IP  →  stored in .env as VM_PUBLIC_IP
VM user       →  azureuser
VM OS         →  Ubuntu 22.04 LTS
VM size       →  Standard_B2ms (2 vCPU, 8 GB RAM)
Working dir   →  ~/noc-sentinel-lab
```

---

## Stack — Exact Versions

| Service | Image | Port | Purpose |
|---|---|---|---|
| FastAPI app | python:3.11-slim (custom) | 8000 | HTTP monitoring target |
| PostgreSQL | postgres:15 | 5432 | Database target + Zabbix backend |
| Zabbix Server | zabbix/zabbix-server-pgsql:6.4-ubuntu-latest | 10051 | Infrastructure monitoring engine |
| Zabbix Web | zabbix/zabbix-web-nginx-pgsql:6.4-ubuntu-latest | 8080 | Zabbix frontend UI |
| Zabbix Agent 2 | zabbix/zabbix-agent2:6.4-ubuntu-latest | 10050 | Host metrics collection |
| Prometheus | prom/prometheus:v2.45.0 | 9090 | Metrics scraping |
| Node Exporter | prom/node-exporter:v1.6.1 | 9100 | Host OS metrics |
| Grafana | grafana/grafana:10.0.3 | 3000 | Dashboards + alert rules |
| AlertManager | prom/alertmanager:v0.25.0 | 9093 | Alert routing |
| Webhook Bridge | python:3.11-slim (custom) | 8001 | Grafana → Jira integration |

**Never upgrade versions mid-project without updating this file and testing.**

---

## Directory Structure

```
noc-sentinel-lab/
├── CLAUDE.md                    ← you are here
├── plan.md                      ← 1-day execution plan
├── docker-compose.yml           ← single source of truth for all services
├── .env                         ← secrets (never commit this file)
├── .env.example                 ← committed template, no real values
├── .gitignore
│
├── terraform/
│   ├── main.tf                  ← Azure VM + NSG + public IP
│   ├── variables.tf
│   ├── outputs.tf               ← outputs VM public IP
│   └── terraform.tfstate        ← never commit this
│
├── services/
│   ├── fastapi-app/
│   │   ├── Dockerfile
│   │   ├── main.py              ← FastAPI app code
│   │   └── requirements.txt
│   │
│   └── webhook-bridge/
│       ├── Dockerfile
│       ├── main.py              ← Grafana webhook → Jira bridge
│       └── requirements.txt
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml       ← scrape configs
│   ├── alertmanager/
│   │   └── alertmanager.yml     ← routing + receivers
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   │   └── prometheus.yml
│       │   ├── dashboards/
│       │   │   └── dashboards.yml
│       │   └── alerting/
│       │       └── alert-rules.yml
│       └── dashboards/
│           └── noc-main.json    ← NOC operations dashboard JSON
│
├── zabbix/
│   └── setup.py                 ← Zabbix API configuration script
│
├── runbooks/
│   ├── runbook-service-down.md
│   ├── runbook-high-cpu.md
│   └── runbook-disk-critical.md
│
└── scripts/
    ├── simulate-cpu.sh           ← triggers HIGH CPU alert
    ├── simulate-disk.sh          ← triggers DISK CRITICAL alert
    ├── simulate-service-down.sh  ← stops FastAPI container
    └── resolve-all.sh            ← cleans up all simulated incidents
```

---

## Environment Variables

All secrets live in `.env`. Never hardcode them.

```bash
# .env structure — see .env.example for all keys

# Azure
VM_PUBLIC_IP=<set after terraform apply>

# PostgreSQL (shared by app and Zabbix)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=noc_lab
POSTGRES_USER=noc_user
POSTGRES_PASSWORD=<secret>

# Zabbix
ZABBIX_DB_NAME=zabbix
ZABBIX_DB_USER=zabbix
ZABBIX_DB_PASSWORD=<secret>
ZBX_SERVER_HOST=zabbix-server
ZBX_SERVER_NAME=NOC-Sentinel-Lab

# Grafana
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=<secret>
GF_SERVER_ROOT_URL=http://${VM_PUBLIC_IP}:3000

# AlertManager — Gmail SMTP
ALERTMANAGER_SMTP_FROM=<gmail>
ALERTMANAGER_SMTP_PASSWORD=<gmail-app-password>
ALERTMANAGER_RECEIVER_EMAIL=<your-email>

# Jira
JIRA_BASE_URL=https://<your-site>.atlassian.net
JIRA_EMAIL=<your-email>
JIRA_API_TOKEN=<token-from-atlassian>
JIRA_PROJECT_KEY=NOC
```

---

## Service Communication Map

Use these exact hostnames inside Docker Compose configs.
Using `localhost` inside compose service configs is a common mistake — it refers to the container itself, not other services.

```
FastAPI app       → postgres:5432
Webhook Bridge    → (external) JIRA_BASE_URL via HTTPS
Zabbix Server     → postgres:5432 (zabbix DB), zabbix-agent:10050
Zabbix Web        → zabbix-server:10051, postgres:5432
Zabbix Agent      → zabbix-server:10051 (active checks)
Prometheus        → node-exporter:9100, fastapi-app:8000/metrics
Grafana           → prometheus:9090, alertmanager:9093
AlertManager      → (external) SMTP, webhook-bridge:8001
```

---

## Coding Standards

### Python (FastAPI app + Webhook Bridge)

- Python 3.11
- Use `httpx` for async HTTP calls, `requests` for sync scripts
- All environment variables via `os.getenv()` — never hardcoded
- Every endpoint returns `{"status": "...", "timestamp": "...", "service": "..."}` JSON shape
- Health endpoint must return HTTP 200 when healthy, HTTP 503 when degraded
- Log format: `[TIMESTAMP] [LEVEL] [SERVICE] message` — use Python `logging` module
- Dockerfile: use `python:3.11-slim`, never `python:3.11` (too large for this VM)
- Always include a `requirements.txt` — no implicit dependencies

```python
# Standard health endpoint pattern — use this shape everywhere
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "fastapi-app",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

### Prometheus metrics endpoint (FastAPI)

- Use `prometheus-fastapi-instrumentator` library
- Expose at `/metrics` (default Prometheus path)
- Add custom business metric: `noc_incidents_total` counter
- Add custom gauge: `noc_app_simulated_load` (0.0 to 1.0)

### Docker Compose

- All services must have `restart: unless-stopped`
- All services must have a `healthcheck` block
- Use named volumes for all persistent data (Zabbix, Prometheus, Grafana, Postgres)
- Never use `host` network mode — use the default bridge network
- Service names must be lowercase with hyphens: `zabbix-server`, `node-exporter`
- Always pin image tags — never use `:latest`

```yaml
# Standard healthcheck pattern for HTTP services
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:PORT/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Prometheus Configuration

- Scrape interval: `15s` globally
- Evaluation interval: `15s`
- Job names must match service names: `fastapi-app`, `node-exporter`
- All scrape targets use Docker service names + port
- Alert rules file: `monitoring/grafana/provisioning/alerting/alert-rules.yml`

```yaml
# Standard scrape job pattern
- job_name: 'fastapi-app'
  static_configs:
    - targets: ['fastapi-app:8000']
  metrics_path: '/metrics'
  scrape_interval: 15s
```

### Grafana Dashboards

- All dashboards provisioned via JSON files — never create dashboards manually in UI without exporting
- Dashboard UID format: `noc-[purpose]` (e.g., `noc-main`, `noc-zabbix`)
- Refresh: `30s` for operational dashboards
- Default time range: `Last 1 hour`
- Panel title case: sentence case only (e.g., "CPU usage %" not "CPU Usage %")
- Stat panels: always configure thresholds — green/yellow/red. No un-thresholded stat panels.
- Color scheme: red = critical, yellow/orange = warning, green = healthy

### Grafana Alert Rules

- Alert rule name format: `[SERVICE] [CONDITION]` (e.g., `FastAPI service down`, `Host CPU high`)
- Labels required on every rule: `team=noc`, `severity=critical|warning`
- Annotations required: `summary`, `description`, `runbook_url`
- Pending period: 1m for critical, 3m for warning (avoid flapping)
- All rules route to AlertManager contact point

```yaml
# Runbook URL pattern in annotations
runbook_url: "https://github.com/ahmedmarzouki1993/noc-sentinel-lab/blob/main/runbooks/runbook-[name].md"
```

### Terraform

- Provider: `azurerm` ~> 3.0
- Resource group name: `noc-lab-rg`
- All resource names prefixed: `noc-sentinel-`
- Tags on every resource: `project = "noc-sentinel-lab"`, `env = "lab"`, `owner = "ahmed-marzouki"`
- State: local (`terraform.tfstate`) — do not configure remote backend for this lab
- Never auto-approve in scripts — always run `terraform plan` first, then `terraform apply`

### Runbooks

- All runbooks in `runbooks/` directory
- Filename: `runbook-[incident-type].md`
- Every runbook must contain exactly these sections in order:
  1. Overview
  2. Severity & SLA
  3. Prerequisites
  4. Detection signals
  5. Initial triage (first 2 minutes)
  6. Investigation commands
  7. Resolution steps
  8. Verification
  9. Escalation criteria
  10. Post-incident actions
  11. Revision history
- All commands in runbooks must be tested and working — no placeholder commands
- SLA targets: P1 detect <5min / resolve <30min | P2 detect <10min / resolve <60min

---

## Common Tasks

### Start the full stack
```bash
cd ~/noc-sentinel-lab
docker compose up -d
docker compose ps   # verify all healthy
```

### Check all service logs at once
```bash
docker compose logs --follow --tail=50
```

### Check a specific service
```bash
docker compose logs [service-name] --tail=100
```

### Restart a single service without full restart
```bash
docker compose restart [service-name]
```

### Run incident simulation
```bash
bash scripts/simulate-service-down.sh    # P1 scenario
bash scripts/simulate-cpu.sh             # P2 scenario
bash scripts/simulate-disk.sh            # P1 scenario
bash scripts/resolve-all.sh              # clean up everything
```

### Re-run Zabbix API setup (idempotent)
```bash
docker compose exec zabbix-server python3 /scripts/setup.py
```

### Deploy AlertManager after credential change
AlertManager v0.25.0 does not support env var expansion in config files.
Always run envsubst on the VM before recreating the container:
```bash
cd ~/noc-sentinel-lab
set -a && source .env && set +a
envsubst < monitoring/alertmanager/alertmanager.yml > /tmp/am-resolved.yml
cp /tmp/am-resolved.yml monitoring/alertmanager/alertmanager.yml
docker compose rm -sfv alertmanager
docker compose up -d alertmanager
```
The local `monitoring/alertmanager/alertmanager.yml` is the template (with `${}`).
Never commit the resolved version — it contains plaintext credentials.

### Export Grafana dashboard to JSON
```bash
curl -s -u admin:${GF_SECURITY_ADMIN_PASSWORD} \
  http://localhost:3000/api/dashboards/uid/noc-main \
  | jq '.dashboard' > monitoring/grafana/dashboards/noc-main.json
```

### Rebuild a custom service after code change
```bash
docker compose build [fastapi-app|webhook-bridge]
docker compose up -d [fastapi-app|webhook-bridge]
```

### SSH to VM
```bash
ssh azureuser@$(grep VM_PUBLIC_IP .env | cut -d= -f2)
```

### Stop VM at end of day (saves Azure credits)
```bash
az vm deallocate --resource-group noc-lab-rg --name noc-sentinel-vm
```

---

## Debugging Reference

### Service name reference
The FastAPI service name in Docker Compose is `fastapi-app` (not `app`).
Always use `docker compose stop fastapi-app` / `docker compose start fastapi-app`.

### Alert not firing in Grafana
1. Check Prometheus has data: `http://localhost:9090/graph` — query the metric manually
2. Check alert rule pending period — might still be in "Pending" state
3. Check Grafana → Alerting → Alert rules → expand the rule → see evaluation log
4. Verify AlertManager is reachable: `curl http://localhost:9093/-/healthy`

### Zabbix not collecting host metrics
```bash
# Test agent from server side
docker compose exec zabbix-server zabbix_get -s zabbix-agent -p 10050 -k system.hostname
# Should return the container hostname, not an error
```

### Jira ticket not auto-created
```bash
# Test webhook bridge manually
curl -X POST http://localhost:8001/webhook/grafana-alert \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "labels": {"alertname": "TestAlert", "severity": "critical", "service": "fastapi"},
    "annotations": {"summary": "Manual test alert"}
  }'
# Should return {"ticket_created": true, "issue_key": "NOC-X"}
```

### Container running but service not responding
```bash
docker compose exec [service] curl -sf http://localhost:[port]/health
# If this fails, the service crashed inside the container
# Check logs: docker compose logs [service] --tail=50
```

### PostgreSQL connection issues
```bash
docker compose exec postgres psql -U noc_user -d noc_lab -c "SELECT 1"
# If this fails, check POSTGRES_* env vars in .env
```

### Prometheus not scraping a target
```bash
# Check targets page
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job:.labels.job, health:.health, lastError:.lastError}'
```

---

## Security Notes

- `.env` is in `.gitignore` — never remove this rule
- Zabbix default credentials (Admin/zabbix) must be changed on first login
- Grafana admin password must be set in `.env` — never leave as `admin/admin` on a public IP
- Azure NSG limits access to ports 8080, 3000, 9090 — do not open these to 0.0.0.0/0 in production
- This is a lab environment — credentials here are for learning only, never reuse in production
- Jira API token: rotate it after the project is complete

---

## Known Limitations

- Zabbix Agent monitors the container filesystem, not the VM host filesystem directly.
  For host-level disk monitoring, rely on Node Exporter + Grafana/Prometheus stack.
- AlertManager email delivery requires a Gmail App Password, not your main Gmail password.
  Generate one at: https://myaccount.google.com/apppasswords
- Jira free tier limits: 10 users, no automation rules on free plan.
  Use the webhook bridge (webhook-bridge service) for Grafana → Jira automation instead.
- Standard_B2ms has 8GB RAM. If all services start simultaneously, allow 3-4 minutes
  for all healthchecks to pass — Zabbix Server is particularly slow to initialize.

---

## Project Context for Interview

When asked about this project in an interview, frame it as:

> "I built a full NOC simulation lab on Azure to deepen my hands-on experience with the
> tools used in production NOC environments. The stack covers the full incident lifecycle:
> Zabbix for infrastructure monitoring, Prometheus and Grafana for observability and alerting,
> AlertManager for routing, and Jira for ITSM ticket management. I wrote an integration
> layer that automatically creates prioritized Jira tickets when Grafana alerts fire,
> and practiced the full NOC workflow — detect, triage, investigate, resolve, document —
> across four incident scenarios. All runbooks are on GitHub."

Key metrics to mention:
- Mean time to detect (MTTD): < 2 minutes
- 4 incident scenarios practiced end-to-end
- 3 runbooks authored and tested
- Full Grafana → AlertManager → Jira pipeline automated

---

## Outstanding Gaps — Priority Order

Remaining work to match the full NOC Sentinel Lab description:

1. **Zabbix triggers** — Add CPU >80%, RAM >85%, disk >85% triggers inside Zabbix (not just Grafana). Most interview-relevant gap.
2. **Zabbix dashboard** — Create a dashboard in Zabbix UI showing all monitored hosts with CPU/RAM/disk widgets.
3. **CPU + disk simulations end-to-end** — Run `simulate-cpu.sh` and `simulate-disk.sh`, confirm alerts fire and Jira tickets auto-create.
4. **5 manually resolved Jira tickets** — Practice full lifecycle: Open → Assigned → In Progress → Resolved → Closed.
5. **Email alerts confirmed** — Trigger an alert and confirm Gmail receives the AlertManager notification.

---

## What Claude Code Should Never Do in This Project

- Never use `localhost` as a hostname inside docker-compose service configs
- Never commit `.env` or `terraform.tfstate` to git
- Never use `:latest` image tags — always pin versions
- Never generate Grafana dashboards without thresholds on stat panels
- Never write alert rules without `team` and `severity` labels
- Never skip the `healthcheck` block on any Docker service
- Never hardcode credentials — always reference environment variables
- Never modify `plan.md` — it is a historical record of the original execution plan
- Never run `terraform destroy` without explicit instruction from Ahmed
- Never open NSG port 5432 (PostgreSQL) to the internet — internal only

---

*Last updated: initial setup*  
*Stack: Zabbix 6.4 · Prometheus 2.45 · Grafana 10 · AlertManager 0.25 · Jira Cloud · Azure · Docker Compose*
