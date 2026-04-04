import logging
import math
import os
import time
from datetime import datetime

import psycopg2
from fastapi import FastAPI, Response
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [fastapi-app] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(title="NOC Sentinel — FastAPI App", version="1.0.0")

# ──────────────────────────────────────────────
# Prometheus custom metrics
# ──────────────────────────────────────────────
noc_incidents_total = Counter(
    "noc_incidents_total",
    "Total number of incidents recorded",
    ["severity"],
)
noc_app_simulated_load = Gauge(
    "noc_app_simulated_load",
    "Simulated application load (0.0 to 1.0)",
)

Instrumentator().instrument(app).expose(app)

# ──────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "noc_lab"),
        user=os.getenv("POSTGRES_USER", "noc_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=5,
    )


def check_db_health() -> bool:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        return False


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────
@app.get("/health")
async def health(response: Response):
    db_ok = check_db_health()
    status = "healthy" if db_ok else "degraded"
    if not db_ok:
        response.status_code = 503
        logger.warning("Health check: degraded — DB unreachable")
    else:
        logger.info("Health check: healthy")
    return {
        "status": status,
        "service": "fastapi-app",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {
            "database": "ok" if db_ok else "error",
        },
    }


@app.get("/metrics-test")
async def metrics_test():
    noc_incidents_total.labels(severity="info").inc()
    return {
        "status": "ok",
        "service": "fastapi-app",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Metrics counter incremented",
    }


@app.get("/simulate-load")
async def simulate_load():
    """Burn CPU for ~2 seconds to trigger High CPU alert."""
    noc_app_simulated_load.set(0.9)
    logger.info("Simulating CPU load...")
    start = time.time()
    # CPU-bound work for 2 seconds
    while time.time() - start < 2:
        _ = sum(math.sqrt(i) for i in range(10_000))
    noc_app_simulated_load.set(0.0)
    logger.info("CPU load simulation complete")
    return {
        "status": "ok",
        "service": "fastapi-app",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Load simulation complete",
        "duration_seconds": round(time.time() - start, 2),
    }


@app.get("/incidents")
async def list_incidents():
    """Return incidents from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, severity, status, created_at FROM incidents ORDER BY created_at DESC LIMIT 20"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        incidents = [
            {
                "id": r[0],
                "title": r[1],
                "severity": r[2],
                "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        noc_incidents_total.labels(severity="query").inc()
        return {
            "status": "ok",
            "service": "fastapi-app",
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(incidents),
            "incidents": incidents,
        }
    except Exception as exc:
        logger.error("Failed to fetch incidents: %s", exc)
        return {
            "status": "error",
            "service": "fastapi-app",
            "timestamp": datetime.utcnow().isoformat(),
            "message": str(exc),
        }
