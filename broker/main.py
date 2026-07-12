"""PCOS Context Broker — FastAPI service entry point.

Endpoints:
  POST /route          — route a task, get RoutingDecision
  POST /execute        — route + plan a task, get ExecutionPlan
  POST /context/compress — compress context into prompt prefix
  GET  /health         — health check with latency budgets
  GET  /metrics        — latency + local-vs-cloud hit rate metrics
  GET  /memory         — PiecesOS memory status
  POST /memory/query   — query PiecesOS LTM
  WS   /bridge         — Chrome ↔ Android relay hub
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from broker.config import get_settings
from broker.logging import get_logger, setup_logging
from broker.routers._shared import get_db
from broker.routers.route_router import router as route_router
from broker.routers.ops_router import router as ops_router
from broker.routers.bridge_router import router as bridge_router

_settings = get_settings()
_log = get_logger("broker.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _log.info("broker_starting", host=_settings.broker_host, port=_settings.broker_port)
    get_db()
    _log.info("broker_ready")
    yield
    _log.info("broker_shutdown")


app = FastAPI(title="PCOS Context Broker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(route_router)
app.include_router(ops_router)
app.include_router(bridge_router)


def run():
    """Entry point for pcos-broker CLI."""
    import uvicorn
    uvicorn.run(
        "broker.main:app",
        host=_settings.broker_host,
        port=_settings.broker_port,
        log_level=_settings.broker_log_level,
    )
