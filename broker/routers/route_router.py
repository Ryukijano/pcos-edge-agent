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
    # Enrich context with PiecesOS LTM results before routing
    if task.requires_personal_context:
        ltm_hits = await _pieces_connector.query_async(task.text, top_k=5)
        if ltm_hits:
            ctx.memory.piecesos_hits = ltm_hits
            decision = route(task, ctx)
            decision.context_payload["ltm_results"] = ltm_hits
        else:
            decision = route(task, ctx)
    else:
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


@router.get("/memory/query")
async def memory_query(q: str, top_k: int = 5):
    """Query PiecesOS LTM via MCP.

    Returns relevant workflow memories (code snippets, chats, links)
    from the local PiecesOS Long-Term Memory engine. All results are
    PII-stripped before returning.
    """
    results = await _pieces_connector.query_async(q, top_k=top_k)
    return {"query": q, "results": results, "count": len(results)}


@router.post("/context/compress")
async def compress_context(ctx: dict):
    context = PCOSContext(**ctx)
    return {"prompt_prefix": context.to_prompt_prefix()}


@router.get("/litert_server/models")
async def litert_server_models():
    """List available models from local LiteRT-LM server (lit serve).

    Proxies GET /v1/models from the OpenAI-compatible server on port 9379.
    """
    import httpx
    server_url = _settings.litert_server_url if hasattr(_settings, 'litert_server_url') else "http://localhost:9379"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{server_url}/v1/models")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        _log.warning("litert_server_models_unavailable", error=str(e))
        return {"models": [], "error": str(e)}


@router.post("/litert_server/infer")
async def litert_server_infer(prompt: str, system_prompt: str = "", model_id: str = "gemma4-e2b", backend: str = "gpu", max_tokens: int = 8192):
    """Proxy inference to a local LiteRT-LM server (lit serve).

    Uses the OpenAI-compatible /v1/chat/completions endpoint.
    The model field supports: model_id[,backend][,max_tokens]
    Example: "gemma4-e2b,gpu,4096" or "gemma4-12b,gpu,8192"
    """
    import httpx
    server_url = _settings.litert_server_url if hasattr(_settings, 'litert_server_url') else "http://localhost:9379"
    model_field = f"{model_id},{backend},{max_tokens}"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{server_url}/v1/chat/completions",
                json={
                    "model": model_field,
                    "messages": messages,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {
                "result": text,
                "surface": "litert_server",
                "local": True,
                "model": data.get("model", model_id),
                "usage": usage,
            }
    except Exception as e:
        _log.warning("litert_server_unavailable", error=str(e))
        return {"result": f"[LiteRT server unavailable: {e}]", "surface": "litert_server", "local": False}


@router.post("/litert_server/chat/stream")
async def litert_server_chat_stream(prompt: str, system_prompt: str = "", model_id: str = "gemma4-e2b", backend: str = "gpu", max_tokens: int = 8192):
    """Stream inference from local LiteRT-LM server via SSE.

    Uses OpenAI-compatible /v1/chat/completions with stream=true.
    Returns Server-Sent Events (SSE) chunks.
    """
    import httpx
    from fastapi.responses import StreamingResponse
    import json

    server_url = _settings.litert_server_url if hasattr(_settings, 'litert_server_url') else "http://localhost:9379"
    model_field = f"{model_id},{backend},{max_tokens}"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{server_url}/v1/chat/completions",
                    json={
                        "model": model_field,
                        "messages": messages,
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield line + "\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
