# NOC Sentinel Lab — 1-Day Execution Plan
**Role:** Senior NOC Engineer  
**Target:** Fully operational NOC stack in a single working day  
**Assistant:** Claude Code (claude.ai/code) for all code generation and configuration  

---

## Architecture Decision

> **Single Azure VM + Docker Compose** — not 3 VMs.
>
> Spinning up 3 VMs, configuring networking, SSH keys, and firewall rules burns 4+ hours.
> A single VM running all services in Docker Compose gets everything wired and observable in under 2 hours.
> Same tools, same skills, zero wasted time on infrastructure plumbing.

```
┌─────────────────────────────────────────────────────────┐
│                  Azure VM (Ubuntu 22.04)                 │
│                    Standard B2ms                         │
│                  2 vCPU / 8 GB RAM                       │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  FastAPI App │  │  PostgreSQL  │  │  Zabbix Agent │  │
│  │   :8000      │  │   :5432      │  │   :10050      │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │Zabbix Server │  │  Prometheus  │  │    Grafana    │  │
│  │ + Zabbix Web │  │   :9090      │  │    :3000      │  │
│  │   :8080      │  └──────────────┘  └───────────────┘  │
│  └──────────────┘                                        │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ Node Exporter│  │AlertManager  │                     │
│  │   :9100      │  │   :9093      │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘

External (cloud, free):
┌──────────────┐
│  Jira Cloud  │  ← Free personal tier
│  (browser)   │
└──────────────┘
```

---

## Pre-Flight Checklist (Before You Start)

- [ ] Azure Student account accessible and credits available
- [ ] Claude Code installed (`npm install -g @anthropic-ai/claude-code`)
- [ ] Jira account created at https://www.atlassian.com/software/jira (free tier)
- [ ] Local SSH key ready (`~/.ssh/id_rsa.pub`)
- [ ] Git installed locally

**Estimated credits usage:** Standard B2ms (~$0.096/hr) × 10 hrs = ~$1 from your student credits. Negligible.

---

## Day Schedule

| Time | Phase | Deliverable |
|---|---|---|
| 09:00 – 09:30 | Phase 0 | Azure VM provisioned via Terraform |
| 09:30 – 11:00 | Phase 1 | Full Docker Compose stack running |
| 11:00 – 12:30 | Phase 2 | Zabbix configured — hosts, triggers, dashboards |
| 12:30 – 13:00 | Break | — |
| 13:00 – 14:30 | Phase 3 | Grafana NOC dashboard + alert rules live |
| 14:30 – 15:30 | Phase 4 | Jira project + alert webhook integration |
| 15:30 – 16:30 | Phase 5 | Incident simulation — 3 full scenarios |
| 16:30 – 17:30 | Phase 6 | Runbooks + GitHub push |
| 17:30 – 18:00 | Phase 7 | CV bullet points written |

---

## Phase 0 — Azure VM Provisioning (09:00–09:30)

**Goal:** One Ubuntu VM, public IP, ports open, SSH working.

### Claude Code Prompt:
```
Write Terraform code to provision a single Azure VM with these specs:
- Ubuntu 22.04 LTS
- Size: Standard_B2ms
- Region: West Europe or Qatar North
- Public IP with DNS label "noc-sentinel-lab"
- NSG inbound rules open for ports: 22, 80, 3000, 8080, 9090, 9093, 8000
- SSH key authentication using my local public key
- Output the public IP address
Use azurerm provider, store state locally for simplicity.
```

### Execute:
```bash
cd ~/noc-sentinel-lab/terraform
terraform init
terraform apply -auto-approve
# Copy the output public IP — you'll use it everywhere below
export VM_IP=$(terraform output -raw public_ip)
```

### Validate:
```bash
ssh azureuser@$VM_IP "echo 'VM is alive'"
```

---

## Phase 1 — Docker Compose Stack (09:30–11:00)

**Goal:** All 7 services running and healthy in containers.

### Claude Code Prompt:
```
Write a production-quality docker-compose.yml for a NOC lab environment containing:
1. FastAPI app (Python) with endpoints: GET /health, GET /metrics-test, GET /simulate-load
   that returns JSON status and simulates CPU work on /simulate-load
2. PostgreSQL 15 with a sample "incidents" table pre-seeded with 10 rows
3. Zabbix Server 6.4 (zabbix/zabbix-server-pgsql) using the PostgreSQL above as backend
4. Zabbix Web frontend (zabbix/zabbix-web-nginx-pgsql) on port 8080
5. Zabbix Agent 2 (zabbix/zabbix-agent2) monitoring the host
6. Prometheus 2.45 scraping node_exporter and the FastAPI app
7. Node Exporter for host metrics
8. Grafana 10 with anonymous access disabled, admin/admin credentials
9. AlertManager 0.25 with a simple email receiver config (use Gmail SMTP)

Use named volumes for persistence. Add health checks to all services.
Include a .env file template for secrets.
```

### On the VM:
```bash
ssh azureuser@$VM_IP
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git
sudo usermod -aG docker azureuser
newgrp docker

mkdir ~/noc-sentinel-lab && cd ~/noc-sentinel-lab
# Paste docker-compose.yml generated by Claude Code
docker compose up -d
docker compose ps  # All services should show "healthy" within 3 minutes
```

### Validate all ports:
```bash
curl http://localhost:8000/health          # FastAPI
curl http://localhost:9090/-/healthy       # Prometheus
curl http://localhost:9100/metrics         # Node Exporter
# Open in browser:
# http://$VM_IP:8080   → Zabbix Web (Admin/zabbix)
# http://$VM_IP:3000   → Grafana (admin/admin)
```

**Checkpoint:** If any container is unhealthy, run `docker compose logs [service]` and paste the error to Claude Code for diagnosis.

---

## Phase 2 — Zabbix Configuration (11:00–12:30)

**Goal:** Zabbix monitors the FastAPI app and the host. Two triggers firing correctly.

### Step 2.1 — Connect Agent to Server

Claude Code Prompt:
```
Write a Python script using the Zabbix API (requests library) that:
1. Authenticates to Zabbix at http://localhost:8080 with Admin/zabbix
2. Creates a host group called "NOC-Lab-Targets"
3. Creates a host "fastapi-app" pointing to the Zabbix agent on localhost
4. Links it to the "Linux servers" and "NOC-Lab-Targets" template groups
5. Creates a custom item: HTTP check on http://localhost:8000/health (type=HTTP agent)
6. Creates 2 triggers:
   - CRITICAL: FastAPI /health returns non-200 for 1 minute
   - WARNING: Host CPU utilization > 75% for 2 minutes
7. Creates an action that sends an alert email when any CRITICAL trigger fires
Print confirmation after each step.
```

### Step 2.2 — Zabbix Dashboard

In Zabbix Web UI (http://$VM_IP:8080):
1. Go to **Monitoring → Dashboard → Create dashboard**
2. Add these widgets:
   - **Problems** widget — shows all active alerts
   - **Hosts availability** — green/red per host
   - **Graph** widget — CPU utilization (last 1 hour)
   - **Clock** widget — UTC time (NOC standard)
3. Name it: `NOC Operations Center`

### Step 2.3 — Test a Trigger

```bash
# Simulate a problem: stop the FastAPI container
docker compose stop app
# Wait 90 seconds, check Zabbix → Monitoring → Problems
# You should see a CRITICAL alert for "fastapi-app"
# Restart and verify it auto-resolves
docker compose start app
```

**Checkpoint:** A CRITICAL problem appears in Zabbix within 2 minutes of stopping the service.

---

## Phase 3 — Grafana NOC Dashboard (13:00–14:30)

**Goal:** A real NOC-style board with color-coded status panels and working alert rules.

### Step 3.1 — Prometheus Datasource

In Grafana (http://$VM_IP:3000):
- Configuration → Data sources → Add Prometheus → URL: `http://prometheus:9090`
- Save & Test → should show green

### Step 3.2 — NOC Dashboard

Claude Code Prompt:
```
Write a Grafana dashboard JSON (provisioning format) for a NOC operations board.
Include these panels:

Row 1 — Service Health (stat panels with traffic-light thresholds):
- FastAPI app uptime (up{job="fastapi"} — green if 1, red if 0)
- PostgreSQL up (green/red)
- System load average (green <1, yellow 1-2, red >2)
- Available disk % (green >30%, yellow 10-30%, red <10%)

Row 2 — Performance Metrics (time series graphs):
- CPU usage % (last 1 hour)
- Memory usage % (last 1 hour)
- HTTP request rate on FastAPI (requests/sec)
- Node Exporter network bytes in/out

Row 3 — Alerts (alert list panel):
- All firing Grafana alerts

Use Prometheus as datasource uid "prometheus".
Set refresh to 30s, time range last 1 hour.
```

Import the JSON via Grafana → Dashboards → Import.

### Step 3.3 — Alert Rules

Claude Code Prompt:
```
Write Grafana alert rule YAML (provisioning format) for these 3 NOC scenarios:

1. "Service Down" — FastAPI up metric = 0 for 1 minute
   Severity: critical, Labels: team=noc, service=fastapi

2. "High CPU" — node CPU idle < 20% (meaning >80% used) for 3 minutes  
   Severity: warning, Labels: team=noc, service=host

3. "Disk Critical" — node filesystem available < 15% for 2 minutes
   Severity: critical, Labels: team=noc, service=host

Route all alerts to AlertManager contact point.
```

**Checkpoint:** Stop the FastAPI container. Within 2 minutes, Grafana Alerting → Alert rules shows "Service Down" in FIRING state with red indicator.

---

## Phase 4 — Jira ITSM Integration (14:30–15:30)

**Goal:** Every Grafana alert automatically creates a Jira ticket. You manage the full incident lifecycle.

### Step 4.1 — Jira Project Setup

In Jira (https://your-site.atlassian.net):
1. Create project → **Scrum** → Name: `NOC Incidents` → Key: `NOC`
2. Create issue types: rename default to match NOC standard:
   - `P1 - Critical` (red)
   - `P2 - High` (orange)
   - `P3 - Medium` (yellow)
3. Create workflow:
   ```
   Open → Assigned → Investigating → Resolved → Closed
   ```
4. Get your API token: https://id.atlassian.com/manage-profile/security/api-tokens

### Step 4.2 — Webhook Bridge

Claude Code Prompt:
```
Write a Python FastAPI webhook receiver that:
1. Listens on POST /webhook/grafana-alert
2. Receives Grafana webhook JSON payload
3. Parses: alert name, state (firing/resolved), severity label, service label
4. If state=firing: creates a Jira issue via REST API
   - Project: NOC
   - Issue type based on severity (critical=P1, warning=P2)
   - Summary: "[FIRING] {alert_name} - {service}"
   - Description includes: alert details, timestamp, runbook link placeholder
   - Priority mapped from severity
5. If state=resolved: searches for open Jira issue with matching summary, transitions it to Resolved
6. Logs every action with timestamp

Use environment variables for: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY
Add this as a new service in the docker-compose.yml on port 8001.
```

### Step 4.3 — Wire Grafana to Webhook

In Grafana → Alerting → Contact points:
- Add contact point → Webhook
- URL: `http://webhook-bridge:8001/webhook/grafana-alert`
- Add to default notification policy

**Checkpoint:** Stop FastAPI → Grafana fires alert → Jira ticket `NOC-1` appears automatically with P1 priority.

---

## Phase 5 — Incident Simulation (15:30–16:30)

Run all 3 scenarios end-to-end. For each one, practice the full NOC workflow.

### NOC Incident Workflow (repeat for every scenario):
```
1. DETECT   — Alert fires in Grafana / Zabbix
2. TRIAGE   — Check dashboard, identify scope
3. TICKET   — Verify Jira ticket auto-created (or create manually)
4. ASSIGN   — Assign ticket to yourself in Jira
5. INVESTIGATE — Run diagnosis commands (below)
6. RESOLVE  — Apply fix
7. VERIFY   — Confirm alert auto-resolves
8. DOCUMENT — Add resolution note in Jira ticket
9. CLOSE    — Transition ticket to Closed
```

---

### Scenario 1 — Service Down (P1 Critical)

```bash
# TRIGGER
docker compose stop app

# INVESTIGATE (NOC commands)
docker compose ps                          # Identify down containers
docker compose logs app --tail=50         # Check last logs before crash
curl -sf http://localhost:8000/health || echo "SERVICE DOWN CONFIRMED"

# RESOLVE
docker compose start app

# VERIFY
watch -n5 'curl -s http://localhost:8000/health'
# Wait for Grafana alert to turn green (within 2 min)
```

**Jira ticket note template:**
```
RESOLUTION NOTES:
- Detected: [timestamp] via Grafana "Service Down" alert
- Root cause: Container stopped (simulated maintenance failure)
- Impact: FastAPI endpoint unavailable for ~3 minutes
- Resolution: Container restarted via docker compose start app
- Preventive action: Add container restart policy (restart: unless-stopped)
- Time to detect: <2 min | Time to resolve: <5 min
```

---

### Scenario 2 — High CPU (P2 Warning)

```bash
# Install stress tool in container
docker compose exec app apt-get install -y stress-ng

# TRIGGER (run inside app container)
docker compose exec app stress-ng --cpu 2 --timeout 120s &

# INVESTIGATE
# Check Grafana CPU panel — should spike to >80%
docker stats --no-stream                   # Real-time container CPU
top                                        # Host-level process view
docker compose exec app ps aux             # Processes inside container

# RESOLVE
docker compose exec app pkill stress-ng

# VERIFY
# Grafana CPU panel returns to baseline
# Zabbix CPU trigger auto-resolves
```

**Key diagnostic skill practiced:** Distinguishing host-level vs container-level CPU.

---

### Scenario 3 — Disk Space Critical (P1 Critical)

```bash
# TRIGGER
docker compose exec app bash -c "dd if=/dev/zero of=/tmp/bigfile bs=1M count=4000"

# INVESTIGATE
df -h                                      # Host disk usage
docker system df                           # Docker disk usage
docker compose exec app df -h             # Container disk usage
du -sh /var/lib/docker/*                  # Find largest Docker directories

# RESOLVE
docker compose exec app rm /tmp/bigfile
docker system prune -f                    # Clean unused Docker layers

# VERIFY
df -h                                      # Confirm disk freed
```

---

### Scenario 4 (Bonus) — Database Connection Loss

```bash
# TRIGGER
docker compose stop postgres

# INVESTIGATE
docker compose logs app --tail=20         # FastAPI will show DB connection errors
curl http://localhost:8000/health         # Returns degraded/error status
docker compose ps                         # Postgres shows as stopped

# RESOLVE
docker compose start postgres

# VERIFY
docker compose logs app --tail=10         # Connection pool reconnected
curl http://localhost:8000/health         # Returns healthy
```

---

## Phase 6 — Runbooks + GitHub (16:30–17:30)

**Goal:** 3 professional runbooks committed to GitHub. This is your NOC portfolio proof.

### Claude Code Prompt:
```
Write 3 professional NOC incident runbooks in Markdown format:

Runbook 1: runbook-service-down.md
- Incident classification: P1 Critical
- Symptoms, initial triage steps
- Investigation commands with expected outputs
- Decision tree: restart vs escalate vs rollback
- Escalation contacts placeholder
- SLA: detect <5min, resolve <30min

Runbook 2: runbook-high-cpu.md  
- Incident classification: P2 Warning
- How to identify if CPU is application, system, or container leak
- Investigation commands
- Resolution options: kill process, scale container, throttle requests
- When to escalate to P1
- SLA: detect <5min, resolve <60min

Runbook 3: runbook-disk-critical.md
- Incident classification: P1 Critical
- Immediate triage: find which directory is growing
- Safe cleanup procedures (logs, tmp, Docker layers)
- What NOT to delete without authorization
- Escalation if disk cannot be freed
- SLA: detect <5min, resolve <45min

Each runbook must have: Overview, Prerequisites, Detection, Investigation, Resolution, Verification, Post-Incident, Revision History sections.
```

### Git Push:
```bash
cd ~/noc-sentinel-lab
git init
git add .
git commit -m "feat: NOC Sentinel Lab — full stack operational"
git remote add origin https://github.com/YOUR_USERNAME/noc-sentinel-lab.git
git push -u origin main
```

### README.md (Claude Code Prompt):
```
Write a README.md for my NOC Sentinel Lab GitHub repository.
Include: project overview, architecture diagram (ASCII), stack table,
how to run (3 commands), screenshots section placeholder,
incident scenarios section, and skills demonstrated section.
Position it as a portfolio project demonstrating NOC engineering skills:
Zabbix, Prometheus, Grafana, AlertManager, Jira ITSM, incident response.
```

---

## Phase 7 — CV Bullet Points (17:30–18:00)

After the project is live, add these to your CV under a new "Key Projects" entry:

```
NOC Sentinel Lab — Azure, Docker, Zabbix, Prometheus, Grafana, Jira  [2025]
• Designed and deployed a full NOC monitoring environment on Azure using Docker Compose,
  integrating Zabbix 6.4 (infrastructure monitoring), Prometheus + Grafana (observability),
  and AlertManager for multi-channel alert routing.
• Configured Zabbix host monitoring with custom triggers for service availability and CPU
  thresholds; built NOC-style Grafana dashboards with traffic-light status panels and 30s refresh.
• Implemented end-to-end incident management pipeline: Grafana alert → webhook bridge →
  automatic Jira ticket creation (P1/P2) with severity mapping and auto-resolution on recovery.
• Authored 3 incident runbooks covering service outage, high CPU, and disk-critical scenarios;
  practiced full NOC workflow (detect → triage → ticket → investigate → resolve → post-mortem)
  across 4 simulated incident scenarios.
• Achieved <2-minute mean time to detect (MTTD) across all scenarios.
```

---

## Troubleshooting Guide

### Docker Compose issues
```bash
docker compose logs [service]             # Check specific service logs
docker compose down && docker compose up -d  # Full restart
docker system prune -f                    # Clean if low on disk
```

### Zabbix not receiving data from agent
```bash
# Check agent connectivity
docker compose exec zabbix-agent zabbix_agent2 -t system.hostname
# Verify Zabbix server can reach agent
docker compose exec zabbix-server nc -zv zabbix-agent 10050
```

### Grafana datasource not connecting
```bash
# Use Docker service names, not localhost, inside compose network
# Prometheus URL should be: http://prometheus:9090
# NOT: http://localhost:9090
```

### Jira webhook not triggering
```bash
docker compose logs webhook-bridge --tail=30
curl -X POST http://localhost:8001/webhook/grafana-alert \
  -H "Content-Type: application/json" \
  -d '{"status":"firing","labels":{"alertname":"TestAlert","severity":"critical"}}'
```

---

## End-of-Day Validation Checklist

- [ ] All 7 Docker containers show healthy in `docker compose ps`
- [ ] Zabbix Web accessible, host visible, at least 1 trigger configured
- [ ] Grafana dashboard shows live metrics with color-coded status panels
- [ ] At least 1 Grafana alert in NORMAL state (green)
- [ ] Jira project `NOC` exists with custom workflow
- [ ] Stop FastAPI → Jira ticket auto-created within 3 minutes
- [ ] 3 incident scenarios simulated with Jira tickets created and closed
- [ ] 3 runbooks committed to GitHub
- [ ] README.md pushed with architecture description
- [ ] CV bullet points written

---

## Cost Control

```bash
# At end of day — STOP (not delete) the VM to preserve your work
az vm deallocate --resource-group noc-lab-rg --name noc-sentinel-vm

# Next time you want to continue
az vm start --resource-group noc-lab-rg --name noc-sentinel-vm

# When fully done — delete everything
terraform destroy -auto-approve
```

**Deallocated VM = zero compute cost. You only pay for the managed disk (~$1-2/month).**

---

## Claude Code Session Tips

1. **Start each Claude Code session** by pasting this context:
   ```
   I am building a NOC lab on Azure. Stack: FastAPI + PostgreSQL (targets),
   Zabbix 6.4 + Prometheus + Grafana + AlertManager (monitoring),
   Jira Cloud (ITSM), all running in Docker Compose on Ubuntu 22.04.
   VM IP: [YOUR_IP]. Working directory: ~/noc-sentinel-lab
   ```

2. **When something breaks**, paste the full error + `docker compose ps` output to Claude Code.

3. **For each phase**, start with the exact prompt provided above — do not paraphrase it.

4. **Use Claude Code for all config files** — do not hand-write Zabbix XML, Grafana JSON, or Prometheus YAML. Let Claude generate them, then validate.

---

*Plan authored from the perspective of a Senior NOC Engineer.*  
*Stack: Zabbix 6.4 · Prometheus 2.45 · Grafana 10 · AlertManager 0.25 · Jira Cloud · Azure*  
*Target: 1 working day, zero prior NOC tooling experience required.*