import logging
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [webhook-bridge] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Config from environment
# ──────────────────────────────────────────────
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "NOC")

SEVERITY_TO_PRIORITY = {
    "critical": "Highest",
    "warning": "High",
    "info": "Medium",
}

SEVERITY_TO_ISSUE_TYPE = {
    "critical": "Incident",
    "warning": "Task",
    "info": "Task",
}

app = FastAPI(title="NOC Sentinel — Webhook Bridge", version="1.0.0")


# ──────────────────────────────────────────────
# Jira helpers
# ──────────────────────────────────────────────
def jira_auth() -> tuple[str, str]:
    return (JIRA_EMAIL, JIRA_API_TOKEN)


def jira_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json"}


async def create_jira_issue(alert_name: str, severity: str, service: str, summary_text: str) -> str:
    priority = SEVERITY_TO_PRIORITY.get(severity.lower(), "High")
    issue_type = SEVERITY_TO_ISSUE_TYPE.get(severity.lower(), "P2 - High")
    summary = f"[FIRING] {alert_name} - {service}"
    description = (
        f"*Alert:* {alert_name}\n"
        f"*Service:* {service}\n"
        f"*Severity:* {severity.upper()}\n"
        f"*Detected at:* {datetime.utcnow().isoformat()} UTC\n\n"
        f"*Summary:* {summary_text}\n\n"
        f"*Runbook:* https://github.com/ahmedmarzouki1993/noc-sentinel-lab/blob/main/runbooks/\n\n"
        f"_Auto-created by NOC Sentinel webhook bridge._"
    )
    payload: dict[str, Any] = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "labels": ["noc-sentinel", severity.lower(), service],
        }
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/2/issue",
            json=payload,
            auth=jira_auth(),
            headers=jira_headers(),
        )
    if resp.status_code not in (200, 201):
        logger.error("Jira create failed: %s — %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=f"Jira API error: {resp.status_code}")
    issue_key: str = resp.json()["key"]
    logger.info("Jira issue created: %s (priority=%s)", issue_key, priority)
    return issue_key


async def resolve_jira_issue(alert_name: str, service: str) -> str | None:
    summary = f"[FIRING] {alert_name} - {service}"
    jql = f'project = {JIRA_PROJECT_KEY} AND summary ~ "{alert_name}" AND status != Closed ORDER BY created DESC'
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/2/search",
            params={"jql": jql, "maxResults": 1},
            auth=jira_auth(),
            headers=jira_headers(),
        )
    if resp.status_code != 200 or not resp.json().get("issues"):
        logger.warning("No open Jira issue found for alert: %s", alert_name)
        return None

    issue = resp.json()["issues"][0]
    issue_key = issue["key"]

    # Get available transitions
    async with httpx.AsyncClient(timeout=10.0) as client:
        tresp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/transitions",
            auth=jira_auth(),
            headers=jira_headers(),
        )
    transitions = tresp.json().get("transitions", [])
    resolve_id = next(
        (t["id"] for t in transitions if "resolve" in t["name"].lower() or "done" in t["name"].lower()),
        None,
    )
    if not resolve_id:
        logger.warning("No resolve transition found for %s", issue_key)
        return issue_key

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/transitions",
            json={"transition": {"id": resolve_id}},
            auth=jira_auth(),
            headers=jira_headers(),
        )
    logger.info("Jira issue resolved: %s", issue_key)
    return issue_key


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "webhook-bridge",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.post("/webhook/grafana-alert")
async def grafana_alert(request: Request):
    payload = await request.json()
    logger.info("Received Grafana webhook: status=%s", payload.get("status"))

    status = payload.get("status", "firing")
    # AlertManager sends labels in alerts[0].labels; fall back to top-level for direct posts
    first_alert = payload.get("alerts", [{}])[0] if payload.get("alerts") else {}
    labels = first_alert.get("labels", payload.get("labels", {}))
    annotations = first_alert.get("annotations", payload.get("annotations", {}))

    alert_name = labels.get("alertname", "UnknownAlert")
    severity = labels.get("severity", "warning")
    service = labels.get("service", "unknown")
    summary_text = annotations.get("summary", "No summary provided")

    if not JIRA_BASE_URL or not JIRA_API_TOKEN:
        logger.warning("Jira not configured — skipping ticket creation")
        return {
            "status": "skipped",
            "reason": "Jira credentials not configured",
            "timestamp": datetime.utcnow().isoformat(),
        }

    if status == "firing":
        issue_key = await create_jira_issue(alert_name, severity, service, summary_text)
        return {
            "status": "ok",
            "ticket_created": True,
            "issue_key": issue_key,
            "timestamp": datetime.utcnow().isoformat(),
        }
    elif status == "resolved":
        issue_key = await resolve_jira_issue(alert_name, service)
        return {
            "status": "ok",
            "ticket_resolved": True,
            "issue_key": issue_key,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return {
        "status": "ok",
        "message": f"Unhandled alert status: {status}",
        "timestamp": datetime.utcnow().isoformat(),
    }
