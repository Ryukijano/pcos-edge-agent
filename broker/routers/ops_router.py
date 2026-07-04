"""Health, metrics, and memory endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from broker.config import get_settings
from broker.logging import get_logger
from broker.policies.escalation import get_escalation_log
from broker.routers._shared import get_db, _db_lock, _db
from memory.pieces import PiecesConnector

router = APIRouter(prefix="", tags=["ops"])
_settings = get_settings()
_log = get_logger("broker.ops")

_pieces_connector = PiecesConnector()


@router.get("/health")
async def health():
    db = get_db()
    db_ok = db is not None
    piecesos_ok = _pieces_connector.is_available()
    all_ok = db_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "service": "pcos-context-broker",
        "version": "0.3.0",
        "dependencies": {
            "piecesos": piecesos_ok,
            "database": db_ok,
        },
        "latency_budgets_ms": {
            "route": _settings.latency_target_route_ms,
            "execute": _settings.latency_target_execute_ms,
            "chrome": _settings.latency_target_chrome_ms,
            "android": _settings.latency_target_android_ms,
            "cloud": _settings.latency_target_cloud_ms,
        },
    }


@router.get("/metrics")
async def metrics():
    async with _db_lock:
        db = get_db()
        rows = db.execute(
            "SELECT surface, COUNT(*) as count, AVG(latency_ms) as avg_latency, "
            "SUM(local) as local_count, SUM(escalated) as escalated_count "
            "FROM request_metrics GROUP BY surface"
        ).fetchall()

        total = db.execute("SELECT COUNT(*) FROM request_metrics").fetchone()[0]
        total_local = db.execute("SELECT SUM(local) FROM request_metrics").fetchone()[0] or 0
        total_cloud = db.execute("SELECT SUM(escalated) FROM request_metrics").fetchone()[0] or 0

    by_surface = {}
    for row in rows:
        by_surface[row[0]] = {
            "count": row[1],
            "avg_latency_ms": round(row[2], 2) if row[2] else 0,
            "local_count": row[3],
            "escalated_count": row[4],
        }

    escalations = [e.model_dump() for e in get_escalation_log()]

    return {
        "total_requests": total,
        "local_hit_rate": round(total_local / total, 2) if total else 1.0,
        "cloud_escalation_rate": round(total_cloud / total, 2) if total else 0.0,
        "by_surface": by_surface,
        "recent_escalations": escalations[-10:],
    }


@router.get("/memory")
async def memory_status():
    available = _pieces_connector.is_available()
    if not available:
        return {"available": False, "items": []}
    snippets = _pieces_connector.get_recent_snippets(limit=3)
    projects = _pieces_connector.get_recent_projects(limit=3)
    return {
        "available": True,
        "recent_snippets": snippets,
        "recent_projects": projects,
    }


@router.post("/memory/query")
async def memory_query(body: dict):
    query_text = body.get("query", "")
    top_k = body.get("top_k", 5)
    if not query_text:
        return {"results": []}
    results = await _pieces_connector.query_async(query_text, top_k=top_k)
    return {"results": results}
