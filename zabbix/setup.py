#!/usr/bin/env python3
"""
Zabbix API configuration script — idempotent.
Run after zabbix-server is healthy to configure hosts, templates, triggers.

Usage:
    python3 zabbix/setup.py
    # Or inside the container:
    docker compose exec zabbix-server python3 /scripts/setup.py
"""
import os
import sys
import time
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [zabbix-setup] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

ZABBIX_URL = "http://localhost:8080/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASS = os.getenv("ZABBIX_ADMIN_PASS", "zabbix")


def api_call(method: str, params: dict, auth: str | None = None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    if auth:
        payload["auth"] = auth
    resp = requests.post(ZABBIX_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Zabbix API error: {data['error']}")
    return data["result"]


def wait_for_zabbix(retries: int = 12, delay: int = 10) -> None:
    for i in range(retries):
        try:
            api_call("apiinfo.version", {})
            log.info("Zabbix API is reachable")
            return
        except Exception as exc:
            log.warning("Waiting for Zabbix API (%d/%d): %s", i + 1, retries, exc)
            time.sleep(delay)
    log.error("Zabbix API not reachable after %d retries", retries)
    sys.exit(1)


def get_auth_token() -> str:
    token = api_call("user.login", {"username": ZABBIX_USER, "password": ZABBIX_PASS})
    log.info("Authenticated as %s", ZABBIX_USER)
    return token


def ensure_host_group(auth: str, name: str) -> str:
    existing = api_call("hostgroup.get", {"filter": {"name": [name]}}, auth)
    if existing:
        gid = existing[0]["groupid"]
        log.info("Host group already exists: %s (id=%s)", name, gid)
        return gid
    result = api_call("hostgroup.create", {"name": name}, auth)
    gid = result["groupids"][0]
    log.info("Created host group: %s (id=%s)", name, gid)
    return gid


def get_template_id(auth: str, name: str) -> str | None:
    result = api_call("template.get", {"filter": {"host": [name]}}, auth)
    if result:
        return result[0]["templateid"]
    return None


def ensure_host(auth: str, hostname: str, group_ids: list[str], template_ids: list[str]) -> str:
    existing = api_call("host.get", {"filter": {"host": [hostname]}}, auth)
    if existing:
        hid = existing[0]["hostid"]
        log.info("Host already exists: %s (id=%s)", hostname, hid)
        return hid

    result = api_call(
        "host.create",
        {
            "host": hostname,
            "name": hostname,
            "interfaces": [
                {
                    "type": 1,  # Agent
                    "main": 1,
                    "useip": 0,
                    "ip": "",
                    "dns": "zabbix-agent",
                    "port": "10050",
                }
            ],
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids if tid],
        },
        auth,
    )
    hid = result["hostids"][0]
    log.info("Created host: %s (id=%s)", hostname, hid)
    return hid


def ensure_http_item(auth: str, host_id: str, hostname: str) -> str:
    key = "web.test.error[NOC FastAPI Health]"
    existing = api_call("item.get", {"filter": {"hostid": host_id, "key_": "web.test.error[NOC FastAPI Health]"}}, auth)
    if existing:
        log.info("HTTP check item already exists")
        return existing[0]["itemid"]

    try:
        api_call(
            "httptest.create",
            {
                "name": "NOC FastAPI Health",
                "hostid": host_id,
                "delay": "30s",
                "steps": [
                    {
                        "name": "Check /health",
                        "url": "http://fastapi-app:8000/health",
                        "status_codes": "200",
                        "no": 1,
                    }
                ],
            },
            auth,
        )
        log.info("Created HTTP check web scenario")
    except RuntimeError as exc:
        if "already exists" in str(exc):
            log.info("HTTP check web scenario already exists")
        else:
            raise
    return ""


def ensure_trigger(auth: str, host_id: str, description: str, expression: str, priority: int) -> None:
    existing = api_call("trigger.get", {"filter": {"hostid": host_id, "description": description}}, auth)
    if existing:
        log.info("Trigger already exists: %s", description)
        return
    api_call(
        "trigger.create",
        {
            "description": description,
            "expression": expression,
            "priority": priority,  # 0=not classified, 1=info, 2=warning, 3=average, 4=high, 5=disaster
            "manual_close": 0,
        },
        auth,
    )
    log.info("Created trigger: %s", description)


def main() -> None:
    wait_for_zabbix()
    auth = get_auth_token()

    # Host groups
    noc_group_id = ensure_host_group(auth, "NOC-Lab-Targets")
    existing_linux = api_call("hostgroup.get", {"filter": {"name": ["Linux servers"]}}, auth)
    linux_group_id = existing_linux[0]["groupid"] if existing_linux else noc_group_id

    # Templates
    linux_template_id = get_template_id(auth, "Linux by Zabbix agent")
    if not linux_template_id:
        linux_template_id = get_template_id(auth, "Template OS Linux by Zabbix agent")

    # Host
    host_id = ensure_host(
        auth,
        hostname="noc-sentinel-host",
        group_ids=[noc_group_id, linux_group_id],
        template_ids=[linux_template_id] if linux_template_id else [],
    )

    # HTTP health check web scenario
    ensure_http_item(auth, host_id, "noc-sentinel-host")

    # Zabbix triggers — CPU, memory, disk
    # These use items provided by the "Linux by Zabbix agent" template.
    # Expressions use Zabbix 6.x syntax: func(/host/key, timespan) operator threshold
    ensure_trigger(
        auth,
        host_id,
        description="High CPU utilization (>80% for 3m)",
        expression=f"avg(/noc-sentinel-host/system.cpu.util[,idle],3m)<20",
        priority=3,  # Average
    )
    ensure_trigger(
        auth,
        host_id,
        description="High memory utilization (>85%)",
        expression=f"last(/noc-sentinel-host/vm.memory.utilization)>85",
        priority=3,  # Average
    )
    ensure_trigger(
        auth,
        host_id,
        description="Disk space critical (>85% used on /var/lib/zabbix)",
        expression=f"last(/noc-sentinel-host/vfs.fs.dependent.size[/var/lib/zabbix,pused])>85",
        priority=4,  # High
    )
    ensure_trigger(
        auth,
        host_id,
        description="FastAPI service down (HTTP check failed)",
        expression=f"last(/noc-sentinel-host/web.test.fail[NOC FastAPI Health])<>0",
        priority=5,  # Disaster
    )

    log.info("Zabbix setup complete.")


if __name__ == "__main__":
    main()
