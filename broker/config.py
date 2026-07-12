"""PCOS configuration via pydantic-settings.

All runtime config is loaded from environment variables or a .env file.
This centralises broker URL, PiecesOS settings, latency budgets, and log levels.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PCOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Broker ────────────────────────────────────────────────────
    broker_host: str = "0.0.0.0"
    broker_port: int = 8000
    broker_log_level: str = "info"

    # ── CORS ──────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:8000", "http://localhost:7860"]

    # ── PiecesOS ──────────────────────────────────────────────────
    piecesos_host: str = "localhost"
    piecesos_port: int = 39300
    piecesos_enabled: bool = True
    pieces_mcp_url: str = "http://localhost:39300"

    # ── LiteRT-LM Server (desktop) ────────────────────────────────
    litert_server_url: str = "http://localhost:9379"
    litert_server_12b_model_id: str = "gemma4-12b"
    litert_server_default_model_id: str = "gemma4-e2b"

    # ── Bridge auth ───────────────────────────────────────────────
    bridge_auth_token: str = ""
    bridge_auth_required: bool = False

    # ── Latency budgets (ms) ──────────────────────────────────────
    latency_target_route_ms: int = 50
    latency_target_execute_ms: int = 500
    latency_target_chrome_ms: int = 200
    latency_target_android_ms: int = 1000
    latency_target_cloud_ms: int = 3000

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = True  # structured JSON logs vs plaintext
    log_request_bodies: bool = False

    # ── SQLite ────────────────────────────────────────────────────
    db_path: str = ""  # empty = default data/pcos_metrics.db


@lru_cache
def get_settings() -> Settings:
    return Settings()
