"""PCOS Planner — builds the final prompt and tool plan for the chosen surface.

Given a RoutingDecision + PCOSContext, the planner assembles:
- The system prompt (if any) for the target model
- The user prompt with context prefix injected
- The tool/function declarations (for FunctionGemma)
- Chrome API parameters (for Built-in AI calls)
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from broker.context.context_schema import PCOSContext, TaskObject
from broker.router.router import RoutingDecision, Surface, ChromeAPI


# ── System prompts per surface ─────────────────────────────────

_SYSTEM_PROMPTS = {
    Surface.CHROME_BUILTIN_AI: (
        "You are a precise text transformation assistant. "
        "Operate only on the provided text. Do not add external facts."
    ),
    Surface.CHROME_WEBGPU: (
        "You are a helpful on-device assistant running in the browser via WebGPU. "
        "Answer concisely using the provided context. "
        "You can handle reasoning and longer inputs than the built-in AI APIs."
    ),
    Surface.LITERT_SERVER: (
        "You are a powerful on-device assistant running on a local LiteRT-LM server. "
        "You have more compute and memory than mobile devices. "
        "Provide thorough, well-structured answers."
    ),
    Surface.ANDROID_FUNCTION_GEMMA: (
        "You are an on-device assistant. Use the provided tools when action is needed. "
        "Keep responses concise. Never reveal private data externally."
    ),
    Surface.ANDROID_GEMMA_E2B: (
        "You are a helpful on-device assistant running on Gemma 4 E2B. "
        "Answer concisely using the provided context. "
        "If context is insufficient, say so rather than guessing."
    ),
    Surface.ANDROID_GEMMA_E4B: (
        "You are a helpful on-device assistant running on Gemma 4 E4B. "
        "Answer concisely using the provided context. "
        "You can handle complex reasoning and multimodal inputs. "
        "If context is insufficient, say so rather than guessing."
    ),
    Surface.IOS_GEMMA_E2B: (
        "You are a helpful on-device assistant running on iOS via LiteRT-LM with Metal GPU. "
        "Answer concisely using the provided context. "
        "If context is insufficient, say so rather than guessing."
    ),
    Surface.IOS_GEMMA_E4B: (
        "You are a helpful on-device assistant running on iOS via LiteRT-LM with Metal GPU. "
        "You can process text, images, and audio. "
        "Answer concisely using the provided context. "
        "If context is insufficient, say so rather than guessing."
    ),
    Surface.PIECESOS_MEMORY: (
        "Use the retrieved memories to answer. Cite which memory item was used. "
        "If no relevant memory exists, say so."
    ),
    Surface.CLOUD_LLM: (
        "You are a cloud-based reasoning assistant. The user has explicitly or implicitly "
        "escalated this task. Private identifiers have been stripped."
    ),
}


# ── Chrome API parameter templates ─────────────────────────────

_CHROME_API_PARAMS = {
    ChromeAPI.SUMMARIZER: {
        "type": "key-points",
        "format": "plain-text",
        "length": "short",
    },
    ChromeAPI.TRANSLATOR: {
        "source_language": "auto",
        "target_language": "en",
    },
    ChromeAPI.LANGUAGE_DETECTOR: {},
    ChromeAPI.REWRITER: {
        "tone": "as-is",
    },
    ChromeAPI.PROOFREADER: {},
    ChromeAPI.WRITER: {},
    ChromeAPI.PROMPT: {},
}


# ── FunctionGemma tool declarations ────────────────────────────

FUNCTIONGEMMA_TOOLS = [
    {
        "name": "save_note",
        "description": "Save a text note locally on the device.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The note text to save"},
                "title": {"type": "string", "description": "Optional title for the note"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "create_task",
        "description": "Create a task/todo item with optional due date.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "due_date": {"type": "string", "description": "Optional ISO date (YYYY-MM-DD)"},
                "priority": {"type": "string", "description": "low | medium | high"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "search_memory",
        "description": "Search PiecesOS long-term memory for relevant context.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["query"],
        },
    },
]


class ExecutionPlan(BaseModel):
    surface: str
    system_prompt: str = ""
    user_prompt: str = ""
    chrome_api: Optional[str] = None
    chrome_api_params: dict = Field(default_factory=dict)
    tools: list[dict] = Field(default_factory=list)
    context_prefix: str = ""
    stripped: bool = False

    model_config = {"use_enum_values": True}


def build_plan(
    decision: RoutingDecision,
    task: TaskObject,
    context: Optional[PCOSContext] = None,
) -> ExecutionPlan:
    """Build the final execution plan from a routing decision.

    Args:
        decision: The routing decision from router.route().
        task: The original task object.
        context: Optional full context (for prompt prefix).

    Returns:
        ExecutionPlan ready for the execution layer.
    """
    ctx = context or PCOSContext()
    surface = decision.surface if isinstance(decision.surface, str) else decision.surface.value
    prompt_prefix = decision.context_payload.get("prompt_prefix", "")
    stripped = decision.context_payload.get("stripped", False)

    try:
        system_prompt = _SYSTEM_PROMPTS.get(Surface(surface), "")
    except ValueError:
        system_prompt = ""

    # Build user prompt with context prefix
    if prompt_prefix:
        user_prompt = f"{prompt_prefix}\n\n{task.text}"
    else:
        user_prompt = task.text

    # Chrome API params
    chrome_api = None
    chrome_api_params: dict = {}
    if decision.chrome_api:
        chrome_api = decision.chrome_api.value if hasattr(decision.chrome_api, "value") else str(decision.chrome_api)
        try:
            chrome_api_params = _CHROME_API_PARAMS.get(ChromeAPI(chrome_api), {}).copy()
        except ValueError:
            chrome_api_params = {}

    # Tools for FunctionGemma
    tools: list[dict] = []
    if surface == Surface.ANDROID_FUNCTION_GEMMA.value and task.requires_action:
        tools = FUNCTIONGEMMA_TOOLS

    return ExecutionPlan(
        surface=surface,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        chrome_api=chrome_api,
        chrome_api_params=chrome_api_params,
        tools=tools,
        context_prefix=prompt_prefix,
        stripped=stripped,
    )
