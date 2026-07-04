"""PCOS Context Broker — FastAPI service entry point."""
from fastapi import FastAPI
from pydantic import BaseModel
from broker.router.router import Task, route
from broker.context.context_schema import PCOSContext

app = FastAPI(title="PCOS Context Broker", version="0.1.0")


class RouteRequest(BaseModel):
    task: dict
    context: dict = {}


@app.post("/route")
def route_task(req: RouteRequest):
    task = Task(**req.task)
    decision = route(task)
    return {
        "surface": decision.surface,
        "chrome_api": decision.chrome_api,
        "reason": decision.reason,
        "escalate_to_cloud": decision.escalate_to_cloud,
    }


@app.post("/context/compress")
def compress_context(ctx: dict):
    context = PCOSContext(**ctx)
    return {"prompt_prefix": context.to_prompt_prefix()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "pcos-context-broker"}
