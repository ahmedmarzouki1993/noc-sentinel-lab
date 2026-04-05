# Runbook: Disk Space Critical

## 1. Overview

Available disk space on the VM root filesystem has dropped below 15%.
A full disk causes container crashes, log write failures, and database corruption.
This is a P1 — act immediately.

---

## 2. Severity & SLA

| Attribute | Value |
|---|---|
| Classification | P1 — Critical |
| Detect SLA | < 5 minutes |
| Resolve SLA | < 45 minutes |
| Alert name | `Host disk critical` |
| Alert threshold | < 15% free on `/` |

---

## 3. Prerequisites

- SSH access to the VM: `ssh azureuser@YOUR_VM_PUBLIC_IP`
- Docker CLI access on VM
- Do NOT delete files without identifying what they are first

---

## 4. Detection signals

- **Grafana alert:** `Host disk critical` → FIRING (red)
- **Prometheus query:** `(node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 15`
- **Grafana dashboard:** "Disk available %" stat panel turns red

---

## 5. Initial triage (first 2 minutes)

```bash
ssh azureuser@YOUR_VM_PUBLIC_IP

# 1. Confirm disk usage
df -h /
# Critical: Used% > 85%

# 2. Quick view of largest directories
du -sh /* 2>/dev/null | sort -rh | head -10

# 3. Check if services are still running
docker compose -f ~/noc-sentinel-lab/docker-compose.yml ps
```

---

## 6. Investigation commands

```bash
ssh azureuser@YOUR_VM_PUBLIC_IP

# Find largest directories under /var (most common culprit)
du -sh /var/* 2>/dev/null | sort -rh | head -10

# Docker disk usage breakdown
docker system df

# Find large files (>100MB) across the filesystem
find / -xdev -size +100M -type f 2>/dev/null | sort -k5 -rn

# Check container log sizes
du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -rh | head -10

# Check for simulation artifacts
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app du -sh /tmp/
```

**Common culprits ranked by likelihood:**
1. `/tmp/bigfile` — disk simulation artifact
2. `/var/lib/docker` — unused Docker layers/images
3. Container logs — unbounded log growth
4. `/var/log` — system logs

---

## 7. Resolution steps

### A — Simulation artifact
```bash
docker compose -f ~/noc-sentinel-lab/docker-compose.yml exec fastapi-app rm -f /tmp/bigfile
```

### B — Docker unused layers (safe to clean)
```bash
# Show what will be removed
docker system df

# Remove stopped containers, unused images, unused networks
docker system prune -f

# Also remove unused volumes (WARNING: removes data from stopped containers)
# Only run if you are sure no stopped containers have important data
docker system prune --volumes -f
```

### C — Container logs too large
```bash
# Truncate a specific container log (replace CONTAINER_ID)
CONTAINER_ID=$(docker inspect --format='{{.Id}}' fastapi-app)
truncate -s 0 /var/lib/docker/containers/${CONTAINER_ID}/${CONTAINER_ID}-json.log
```

### D — System logs
```bash
# Check journal size
journalctl --disk-usage

# Vacuum journals older than 7 days
sudo journalctl --vacuum-time=7d

# Clean apt cache
sudo apt-get clean
```

**What NOT to delete without authorization:**
- `/var/lib/docker/volumes/` — named volumes contain Prometheus/Grafana/PostgreSQL data
- `/home/azureuser/noc-sentinel-lab/` — project files
- Any `.env` files

---

## 8. Verification

```bash
# Disk should be above 15% free
df -h /
# Expected: Use% < 85%

# All containers still healthy
docker compose -f ~/noc-sentinel-lab/docker-compose.yml ps
```

Wait 2 minutes — Grafana `Host disk critical` alert auto-resolves.

---

## 9. Escalation criteria

Escalate immediately if:
- Disk is at 100% and no safe files can be identified for deletion
- PostgreSQL logs show write errors (data corruption risk)
- Cannot SSH to VM (disk full prevents login shell)
- Docker volumes cannot be identified as safe to remove

---

## 10. Post-incident actions

1. Document in Jira ticket: what was filling the disk, how much was freed
2. Add log rotation to prevent recurrence:
   ```bash
   # Add to /etc/docker/daemon.json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "50m",
       "max-file": "3"
     }
   }
   sudo systemctl restart docker
   ```
3. Consider increasing VM disk size if growth is structural
4. Close Jira ticket

---

## 11. Revision history

| Date | Author | Change |
|---|---|---|
| 2026-04-05 | Ahmed Marzouki | Initial version — tested against live NOC lab |
