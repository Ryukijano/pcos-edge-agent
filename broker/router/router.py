"""PCOS Context Broker — routing logic.

Deterministic routing decision tree. No LLM reasoning here — just
policy-based dispatch: collect → rank → compress → choose_model → choose_tool.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from broker.context.context_schema import (
    TaskObject, PCOSContext, Modality, Sensitivity, TaskType, NetworkType,
)


class Surface(str, Enum):
    CHROME_BUILTIN_AI = "chrome_builtin_ai"
    CHROME_WEBGPU = "chrome_webgpu"
    ANDROID_FUNCTION_GEMMA = "android_litert_functiongemma"
    ANDROID_GEMMA_E2B = "android_litert_gemma_e2b"
    ANDROID_GEMMA_E4B = "android_litert_gemma_e4b"
    PIECESOS_MEMORY = "piecesos_memory_then_local"
    CLOUD_LLM = "cloud_llm_escalation"


class ChromeAPI(str, Enum):
    PROMPT = "prompt"
    SUMMARIZER = "summarizer"
    TRANSLATOR = "translator"
    LANGUAGE_DETECTOR = "language_detector"
    WRITER = "writer"
    REWRITER = "rewriter"
    PROOFREADER = "proofreader"


class RoutingDecision(BaseModel):
    """The output of the routing decision tree."""
    surface: Surface
    chrome_api: Optional[ChromeAPI] = None
    reason: str = ""
    escalate_to_cloud: bool = False
    context_payload: dict = Field(default_factory=dict)
    tool_plan: list[dict] = Field(default_factory=list)
    latency_target_ms: int = 500

    model_config = {"use_enum_values": True}


# ── Keyword tables for Chrome API selection ────────────────────

_SUMMARIZER_KEYWORDS = {"summarize", "summary", "tldr", "summarise", "brief"}
_TRANSLATOR_KEYWORDS = {"translate", "translation", "in french", "in spanish", "in german", "in japanese", "to french", "to spanish", "to german", "to japanese"}
_LANGUAGE_DETECTOR_KEYWORDS = {"detect language", "what language", "which language", "language detection"}
_REWRITER_KEYWORDS = {"rewrite", "rephrase", "paraphrase", "reword"}
_PROOFREADER_KEYWORDS = {"proofread", "grammar", "correct", "fix typos"}
_WRITER_KEYWORDS = {"write", "draft", "generate", "compose"}


def route(task: TaskObject, context: Optional[PCOSContext] = None) -> RoutingDecision:
    """Core routing decision tree.

    Args:
        task: The task to route.
        context: Optional full PCOSContext for context-aware routing.

    Returns:
        RoutingDecision with surface, API, reason, context_payload, and tool_plan.
    """
    ctx = context or PCOSContext()
    is_offline = ctx.is_offline()

    # 1. Private or offline tasks → Android LiteRT-LM (never leaves device)
    #    Use E4B for reasoning, E2B for transforms (faster, less memory)
    if task.is_private() or is_offline:
        model = Surface.ANDROID_GEMMA_E4B if task.task_type == TaskType.REASONING else Surface.ANDROID_GEMMA_E2B
        return RoutingDecision(
            surface=model,
            reason=f"Private/offline task: stays on device ({model.value})",
            context_payload=_build_payload(ctx, task),
            latency_target_ms=300 if model == Surface.ANDROID_GEMMA_E2B else 1000,
        )

    # 2. Multimodal non-web tasks → Android (Chrome can't do image/audio locally)
    #    E4B has multimodal capabilities, E2B is text-only
    if task.modality in (Modality.IMAGE, Modality.AUDIO) and not task.is_webpage_grounded:
        return RoutingDecision(
            surface=Surface.ANDROID_GEMMA_E4B,
            reason="Multimodal task without browser grounding: Android Gemma 4 E4B handles locally",
            context_payload=_build_payload(ctx, task),
            latency_target_ms=1000,
        )

    # 3. Short browser-grounded transform tasks → Chrome Built-in AI
    #    But if the task needs reasoning or is long, use WebGPU (Gemma 4 in browser)
    if task.is_webpage_grounded and task.is_short and task.task_type == TaskType.TRANSFORM:
        api = _select_chrome_api(task)
        return RoutingDecision(
            surface=Surface.CHROME_BUILTIN_AI,
            chrome_api=api,
            reason=f"Short browser-grounded transform: Chrome {api.value} API",
            context_payload=_build_payload(ctx, task),
            latency_target_ms=500,
        )

    # 3b. Browser-grounded reasoning or long tasks → Chrome WebGPU (Gemma 4 E2B in browser)
    if task.is_webpage_grounded and (task.task_type == TaskType.REASONING or not task.is_short):
        return RoutingDecision(
            surface=Surface.CHROME_WEBGPU,
            reason="Browser-grounded reasoning: Chrome WebGPU (Gemma 4 E2B via LiteRT-LM JS)",
            context_payload=_build_payload(ctx, task),
            latency_target_ms=1000,
        )

    # 4. Personal context tasks → PiecesOS memory first, then local model
    if task.requires_personal_context:
        return RoutingDecision(
            surface=Surface.PIECESOS_MEMORY,
            reason="Task requires personal workflow memory",
            context_payload=_build_payload(ctx, task),
            tool_plan=[{"step": "query_piecesos", "query": task.text, "top_k": 5}],
            latency_target_ms=2000,
        )

    # 5. Function/tool calls → FunctionGemma on device
    if task.requires_action:
        return RoutingDecision(
            surface=Surface.ANDROID_FUNCTION_GEMMA,
            reason="Action/tool call: FunctionGemma on-device",
            context_payload=_build_payload(ctx, task),
            tool_plan=[{"step": "function_call", "model": "functiongemma_270m"}],
            latency_target_ms=300,
        )

    # 6. Explicit user escalation → Cloud (user asked for it)
    if task.user_explicit_escalate:
        return RoutingDecision(
            surface=Surface.CLOUD_LLM,
            reason="User explicitly requested cloud escalation",
            escalate_to_cloud=True,
            context_payload=_build_payload(ctx, task, strip_private=True),
            latency_target_ms=5000,
        )

    # 7. Long reasoning or oversized context → Cloud escalation (last resort)
    if task.exceeds_local_limits or (task.task_type == TaskType.REASONING and not task.is_short):
        return RoutingDecision(
            surface=Surface.CLOUD_LLM,
            reason="Long reasoning or context exceeds local limits",
            escalate_to_cloud=True,
            context_payload=_build_payload(ctx, task, strip_private=True),
            latency_target_ms=5000,
        )

    # 8. Default: local first (Chrome if short + browser-grounded, else Android Gemma)
    if task.is_webpage_grounded and task.is_short:
        return RoutingDecision(
            surface=Surface.CHROME_BUILTIN_AI,
            chrome_api=ChromeAPI.PROMPT,
            reason="Default local inference: Chrome LanguageModel (short, browser-grounded)",
            context_payload=_build_payload(ctx, task),
            latency_target_ms=500,
        )
    # Use E4B for reasoning/complex tasks, E2B for simple transforms
    default_model = Surface.ANDROID_GEMMA_E4B if task.task_type == TaskType.REASONING else Surface.ANDROID_GEMMA_E2B
    return RoutingDecision(
        surface=default_model,
        reason=f"Default local inference: Android {default_model.value}",
        context_payload=_build_payload(ctx, task),
        latency_target_ms=1000 if default_model == Surface.ANDROID_GEMMA_E2B else 2000,
    )


def _select_chrome_api(task: TaskObject) -> ChromeAPI:
    """Pick the right Chrome Built-in AI API for a transform task."""
    text = task.text.lower()
    if any(w in text for w in _SUMMARIZER_KEYWORDS):
        return ChromeAPI.SUMMARIZER
    if any(w in text for w in _TRANSLATOR_KEYWORDS):
        return ChromeAPI.TRANSLATOR
    if any(w in text for w in _LANGUAGE_DETECTOR_KEYWORDS):
        return ChromeAPI.LANGUAGE_DETECTOR
    if any(w in text for w in _REWRITER_KEYWORDS):
        return ChromeAPI.REWRITER
    if any(w in text for w in _PROOFREADER_KEYWORDS):
        return ChromeAPI.PROOFREADER
    if any(w in text for w in _WRITER_KEYWORDS):
        return ChromeAPI.WRITER
    return ChromeAPI.PROMPT


def _build_payload(
    ctx: PCOSContext, task: TaskObject, strip_private: bool = False
) -> dict:
    """Build the context payload for the chosen surface.

    When *strip_private* is True (cloud escalation), PII is redacted.
    """
    payload: dict = {
        "prompt_prefix": ctx.to_prompt_prefix(),
        "task_text": task.text,
        "modality": task.modality.value,
    }
    if strip_private:
        from broker.policies.privacy import strip_pii
        payload["prompt_prefix"] = strip_pii(payload["prompt_prefix"])
        payload["task_text"] = strip_pii(payload["task_text"])
        payload["stripped"] = True
    return payload
