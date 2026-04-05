# NOC Sentinel Lab

A self-contained **Network Operations Center (NOC) simulation lab** deployed on a single Azure VM. Covers the full incident lifecycle: detect → alert → ticket → resolve — using the same tools found in production NOC environments.

---

## Stack

| Service | Version | Port | Role |
|---|---|---|---|
| FastAPI app | python:3.11-slim | 8000 | HTTP monitoring target |
| PostgreSQL | 15 | 5432 | Shared DB for app + Zabbix |
| Zabbix Server | 6.4 | 10051 | Infrastructure monitoring engine |
| Zabbix Web | 6.4 | 8080 | Zabbix UI |
| Zabbix Agent 2 | 6.4 | 10050 | Host metrics collection |
| Prometheus | v2.45.0 | 9090 | Metrics scraping + alert rules |
| Node Exporter | v1.6.1 | 9100 | Host OS metrics |
| Grafana | 10.0.3 | 3000 | Dashboards + alerting |
| AlertManager | v0.25.0 | 9093 | Alert routing (email + webhook) |
| Webhook Bridge | python:3.11-slim | 8001 | AlertManager → Jira integration |

All services run on a single **Azure Standard_D2_v4 VM** (2 vCPU / 8 GB) via Docker Compose.

---

## Alert Pipeline

```
Prometheus ──▶ AlertManager ──▶ Webhook Bridge ──▶ Jira (NOC-XX ticket)
                    │
                    └──▶ Gmail (email notification)
```

1. **Prometheus** evaluates alert rules every 15s (CPU, disk, service availability)
2. **AlertManager** groups and routes firing alerts based on severity
3. **Webhook Bridge** (`services/webhook-bridge/`) translates the alert payload into a Jira issue via REST API
4. **Jira** ticket is created automatically with correct priority (Highest = critical, High = warning)
5. When the alert resolves, the Jira ticket is automatically transitioned to Done

---

## Incident Scenarios

| Script | Scenario | Severity | Expected alert |
|---|---|---|---|
| `simulate-service-down.sh` | Stops FastAPI container | P1 Critical | `FastAPI service down` |
| `simulate-cpu.sh` | Runs stress-ng (2 CPU workers) | P2 Warning | `Host CPU high` |
| `simulate-disk.sh` | Writes large file to container /tmp | P1 Critical | `Host disk critical` |
| `resolve-all.sh` | Cleans up all simulated incidents | — | Alerts auto-resolve |

---

## Project Structure

```
noc-sentinel-lab/
├── docker-compose.yml          # Full stack definition
├── .env.example                # Environment variables template
│
├── terraform/                  # Azure VM provisioning (IaC)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── services/
│   ├── fastapi-app/            # Monitored HTTP service
│   └── webhook-bridge/         # AlertManager → Jira bridge
│
├── monitoring/
│   ├── prometheus/             # Scrape configs + alert rules
│   ├── alertmanager/           # Routing + email/webhook receivers
│   └── grafana/                # Dashboards + provisioned alert rules
│
├── zabbix/
│   ├── setup.py                # Idempotent Zabbix API configuration
│   └── init-zabbix-db.sh       # PostgreSQL init for Zabbix DB
│
├── runbooks/
│   ├── runbook-service-down.md
│   ├── runbook-high-cpu.md
│   └── runbook-disk-critical.md
│
└── scripts/
    ├── simulate-cpu.sh
    ├── simulate-disk.sh
    ├── simulate-service-down.sh
    └── resolve-all.sh
```

---

## Quick Start

### 1. Prerequisites

- Azure subscription + `az` CLI authenticated
- Terraform >= 1.5
- Docker + Docker Compose plugin
- Jira Cloud account (free tier works)
- Gmail account with App Password enabled

### 2. Provision the VM

```bash
cp .env.example .env
# Fill in all YOUR_* values in .env

cd terraform
terraform init
terraform plan
terraform apply
# Note the output public IP → update VM_PUBLIC_IP in .env
```

### 3. Deploy the stack

```bash
# SSH into the VM
ssh azureuser@<VM_PUBLIC_IP>

# Clone the repo
git clone https://github.com/ahmedmarzouki1993/noc-sentinel-lab.git
cd noc-sentinel-lab
cp /path/to/.env .env

# Deploy AlertManager with resolved credentials
set -a && source .env && set +a
envsubst < monitoring/alertmanager/alertmanager.yml > /tmp/am.yml
cp /tmp/am.yml monitoring/alertmanager/alertmanager.yml

# Start all services
docker compose up -d
docker compose ps   # wait for all to be healthy (~3-4 min)
```

### 4. Configure Zabbix

```bash
docker compose exec zabbix-server python3 /scripts/setup.py
```

### 5. Run an incident simulation

```bash
bash scripts/simulate-service-down.sh   # P1 — FastAPI down
bash scripts/simulate-cpu.sh            # P2 — High CPU
bash scripts/simulate-disk.sh           # P1 — Disk critical
bash scripts/resolve-all.sh             # Clean up
```

---

## Access URLs

| Service | URL |
|---|---|
| Grafana | `http://<VM_PUBLIC_IP>:3000` |
| Prometheus | `http://<VM_PUBLIC_IP>:9090` |
| AlertManager | `http://<VM_PUBLIC_IP>:9093` |
| Zabbix Web | `http://<VM_PUBLIC_IP>:8080` |
| FastAPI | `http://<VM_PUBLIC_IP>:8000` |

---

## Runbooks

| Incident | Runbook |
|---|---|
| FastAPI service down | [runbook-service-down.md](runbooks/runbook-service-down.md) |
| High CPU utilization | [runbook-high-cpu.md](runbooks/runbook-high-cpu.md) |
| Disk space critical | [runbook-disk-critical.md](runbooks/runbook-disk-critical.md) |

---

## Teardown

```bash
cd terraform
terraform destroy
```

---

## Author

**Ahmed Marzouki** — Cloud & DevOps Engineer
