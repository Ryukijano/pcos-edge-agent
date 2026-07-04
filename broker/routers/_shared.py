"""Shared metrics and DB utilities for PCOS broker routers."""
from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from broker.config import get_settings

_settings = get_settings()

_DB_PATH = Path(_settings.db_path) if _settings.db_path else Path(__file__).resolve().parent.parent / "data" / "pcos_metrics.db"

_db: Optional[sqlite3.Connection] = None
_db_lock = asyncio.Lock()


def _init_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_metrics (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            surface TEXT NOT NULL,
            chrome_api TEXT,
            task_type TEXT,
            latency_ms REAL,
            local INTEGER NOT NULL,
            escalated INTEGER NOT NULL,
            reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalation_log (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            reason TEXT NOT NULL,
            provider TEXT,
            task_preview TEXT,
            confidence REAL,
            user_explicit INTEGER
        )
    """)
    conn.commit()
    return conn


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = _init_db()
    return _db


async def record_metric(
    surface: str,
    chrome_api: Optional[str],
    task_type: str,
    latency_ms: float,
    local: bool,
    escalated: bool,
    reason: str,
) -> None:
    async with _db_lock:
        db = get_db()
        db.execute(
            "INSERT INTO request_metrics VALUES (?,?,?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                datetime.now(timezone.utc).isoformat(),
                surface,
                chrome_api,
                task_type,
                latency_ms,
                1 if local else 0,
                1 if escalated else 0,
                reason,
            ),
        )
        db.commit()


# ── WebSocket bridge state ─────────────────────────────────────

_bridge_clients: dict[str, object] = {}  # client_id -> ws
