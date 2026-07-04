"""PCOS Context Broker — routing logic."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Surface(str, Enum):
    CHROME_BUILTIN_AI = "chrome_builtin_ai"
    ANDROID_FUNCTION_GEMMA = "android_litert_functiongemma"
    ANDROID_GEMMA_FULL = "android_litert_gemma_full"
    PIECESOS_MEMORY = "piecesos_memory_then_local"
    CLOUD_LLM = "cloud_llm_escalation"


class ChromeAPI(str, Enum):
    PROMPT = "prompt"
    SUMMARIZER = "summarizer"
    CLASSIFIER = "classifier"
    WRITER = "writer"
    REWRITER = "rewriter"
    PROOFREADER = "proofreader"
    MULTIMODAL_PROMPT = "multimodal_prompt"


@dataclass
class Task:
    text: str
    modality: str = "text"          # text | image | audio
    sensitivity: str = "normal"     # private | normal
    task_type: str = "transform"    # transform | action | reasoning | retrieval
    is_short: bool = True
    is_webpage_grounded: bool = False
    requires_personal_context: bool = False
    requires_action: bool = False
    exceeds_local_limits: bool = False
    confidence_threshold: float = 0.7


@dataclass
class RoutingDecision:
    surface: Surface
    chrome_api: Optional[ChromeAPI] = None
    reason: str = ""
    escalate_to_cloud: bool = False


def route(task: Task) -> RoutingDecision:
    """Core routing decision tree."""
    if task.sensitivity == "private" or (task.modality in ["image", "audio"] and not task.is_webpage_grounded):
        return RoutingDecision(
            surface=Surface.ANDROID_FUNCTION_GEMMA,
            reason="Private/offline task: stays on device"
        )
    if task.is_webpage_grounded and task.is_short and task.task_type == "transform":
        api = _select_chrome_api(task)
        return RoutingDecision(
            surface=Surface.CHROME_BUILTIN_AI,
            chrome_api=api,
            reason=f"Short browser-grounded transform: using Chrome {api.value} API"
        )
    if task.requires_personal_context:
        return RoutingDecision(
            surface=Surface.PIECESOS_MEMORY,
            reason="Task requires personal workflow memory"
        )
    if task.requires_action:
        return RoutingDecision(
            surface=Surface.ANDROID_FUNCTION_GEMMA,
            reason="Action/tool call: FunctionGemma on-device"
        )
    if task.exceeds_local_limits or (task.task_type == "reasoning" and not task.is_short):
        return RoutingDecision(
            surface=Surface.CLOUD_LLM,
            reason="Long reasoning or context exceeds local limits",
            escalate_to_cloud=True
        )
    return RoutingDecision(
        surface=Surface.ANDROID_GEMMA_FULL,
        reason="Default local inference"
    )


def _select_chrome_api(task: Task) -> ChromeAPI:
    """Pick the right Chrome Built-in AI API for a transform task."""
    text = task.text.lower()
    if any(w in text for w in ["summarize", "summary", "tldr"]):
        return ChromeAPI.SUMMARIZER
    if any(w in text for w in ["classify", "label", "category", "intent"]):
        return ChromeAPI.CLASSIFIER
    if any(w in text for w in ["rewrite", "rephrase", "paraphrase"]):
        return ChromeAPI.REWRITER
    if any(w in text for w in ["proofread", "grammar", "correct"]):
        return ChromeAPI.PROOFREADER
    if any(w in text for w in ["write", "draft", "generate"]):
        return ChromeAPI.WRITER
    if task.modality in ["image", "audio"]:
        return ChromeAPI.MULTIMODAL_PROMPT
    return ChromeAPI.PROMPT
