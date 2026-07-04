"""Route and execute endpoints."""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from broker.config import get_settings
from broker.logging import get_logger
from broker.context.context_schema import PCOSContext, TaskObject
from broker.router.router import route
from broker.planner.planner import build_plan
from broker.policies.escalation import log_escalation
from broker.routers._shared import record_metric
from memory.pieces import PiecesConnector

router = APIRouter(prefix="", tags=["routing"])
_settings = get_settings()
_log = get_logger("broker.route")

_pieces_connector = PiecesConnector()


class RouteRequest(BaseModel):
    task: dict
    context: dict = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    task: dict
    context: dict = Field(default_factory=dict)


class RouteResponse(BaseModel):
    surface: str
    chrome_api: Optional[str] = None
    reason: str
    escalate_to_cloud: bool = False
    context_payload: dict = Field(default_factory=dict)
    tool_plan: list[dict] = Field(default_factory=list)
    latency_target_ms: int = 500


class ExecuteResponse(BaseModel):
    decision: RouteResponse
    plan: dict
    cloud_result: Optional[str] = None


def _surface_val(decision) -> str:
    return decision.surface if isinstance(decision.surface, str) else decision.surface.value

def _api_val(decision) -> Optional[str]:
    if decision.chrome_api is None:
        return None
    return decision.chrome_api if isinstance(decision.chrome_api, str) else decision.chrome_api.value


@router.post("/route", response_model=RouteResponse)
async def route_task(req: RouteRequest):
    task = TaskObject(**req.task)
    ctx = PCOSContext(**req.context) if req.context else PCOSContext()
    start = time.perf_counter()
    decision = route(task, ctx)
    elapsed_ms = (time.perf_counter() - start) * 1000

    sv = _surface_val(decision)
    _log.info("request_routed", surface=sv, latency_ms=round(elapsed_ms, 2),
              budget_ms=_settings.latency_target_route_ms, task_type=task.task_type)

    await record_metric(
        surface=sv,
        chrome_api=_api_val(decision),
        task_type=task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type),
        latency_ms=elapsed_ms,
        local=not decision.escalate_to_cloud,
        escalated=decision.escalate_to_cloud,
        reason=decision.reason,
    )

    if decision.escalate_to_cloud:
        log_escalation(
            reason=decision.reason,
            task_text=task.text,
            user_explicit=task.user_explicit_escalate,
        )

    return RouteResponse(
        surface=sv,
        chrome_api=_api_val(decision),
        reason=decision.reason,
        escalate_to_cloud=decision.escalate_to_cloud,
        context_payload=decision.context_payload,
        tool_plan=decision.tool_plan,
        latency_target_ms=decision.latency_target_ms,
    )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_task(req: ExecuteRequest):
    task = TaskObject(**req.task)
    ctx = PCOSContext(**req.context) if req.context else PCOSContext()
    start = time.perf_counter()
    decision = route(task, ctx)

    sv = _surface_val(decision)
    if sv == "piecesos_memory_then_local":
        memory_hits = await _pieces_connector.query_async(task.text, top_k=5)
        if memory_hits:
            ctx.memory.piecesos_hits = memory_hits
            decision = route(task, ctx)
            sv = _surface_val(decision)

    plan = build_plan(decision, task, ctx)
    elapsed_ms = (time.perf_counter() - start) * 1000

    _log.info("request_executed", surface=sv, latency_ms=round(elapsed_ms, 2),
              budget_ms=_settings.latency_target_execute_ms, escalated=decision.escalate_to_cloud)

    await record_metric(
        surface=sv,
        chrome_api=_api_val(decision),
        task_type=task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type),
        latency_ms=elapsed_ms,
        local=not decision.escalate_to_cloud,
        escalated=decision.escalate_to_cloud,
        reason=decision.reason,
    )

    if decision.escalate_to_cloud:
        log_escalation(
            reason=decision.reason,
            task_text=task.text,
            user_explicit=task.user_explicit_escalate,
        )

        # Actually call cloud provider if API keys are available
        cloud_result = None
        try:
            from models.cloud.escalation_provider import escalate_to_cloud, get_available_providers
            providers = get_available_providers()
            if providers:
                cloud_result = await escalate_to_cloud(
                    task_text=task.text,
                    system_prompt=plan.system_prompt if hasattr(plan, 'system_prompt') else "",
                    provider=providers[0],
                )
        except Exception as e:
            _log.warning("cloud_escalation_failed", error=str(e))

        return ExecuteResponse(
            decision=RouteResponse(
                surface=sv,
                chrome_api=_api_val(decision),
                reason=decision.reason,
                escalate_to_cloud=decision.escalate_to_cloud,
                context_payload=decision.context_payload,
                tool_plan=decision.tool_plan,
                latency_target_ms=decision.latency_target_ms,
            ),
            plan=plan.model_dump(),
            cloud_result=cloud_result,
        )

    return ExecuteResponse(
        decision=RouteResponse(
            surface=sv,
            chrome_api=_api_val(decision),
            reason=decision.reason,
            escalate_to_cloud=decision.escalate_to_cloud,
            context_payload=decision.context_payload,
            tool_plan=decision.tool_plan,
            latency_target_ms=decision.latency_target_ms,
        ),
        plan=plan.model_dump(),
    )


@router.post("/context/compress")
async def compress_context(ctx: dict):
    context = PCOSContext(**ctx)
    return {"prompt_prefix": context.to_prompt_prefix()}


@router.post("/litert_server/infer")
async def litert_server_infer(prompt: str, system_prompt: str = ""):
    """Proxy inference to a local LiteRT-LM server (lit serve).

    The lit CLI starts a Gemini-compatible API server on port 9379 by default.
    This endpoint forwards prompts to that server, keeping all data local.
    """
    import httpx
    server_url = _settings.litert_server_url if hasattr(_settings, 'litert_server_url') else "http://localhost:9379"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{server_url}/v1beta/models/gemma:generateContent",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]} if system_prompt else None,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"result": text, "surface": "litert_server", "local": True}
    except Exception as e:
        _log.warning("litert_server_unavailable", error=str(e))
        return {"result": f"[LiteRT server unavailable: {e}]", "surface": "litert_server", "local": False}
