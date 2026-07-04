"""PCOS HF Space — interactive demo of the Context Broker routing logic.

This runs a Gradio UI that lets users:
- Enter a task and see which surface it routes to
- Adjust task properties (privacy, context, action) and see routing change
- View the execution plan
- See latency budgets and health status
"""
from __future__ import annotations

import sys
import os

# Add parent dir to path so we can import broker modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from broker.router.router import route, Surface, ChromeAPI
from broker.planner.planner import build_plan
from broker.context.context_schema import PCOSContext, TaskObject, TaskType, Modality, Sensitivity
from broker.config import get_settings

_settings = get_settings()

SURFACE_DESCRIPTIONS = {
    "chrome_builtin_ai": "Chrome Built-in AI — runs in browser, zero network latency",
    "android_litert_functiongemma": "Android FunctionGemma — on-device function calling",
    "android_litert_gemma_full": "Android Gemma 4 — on-device full inference",
    "piecesos_memory_then_local": "PiecesOS Memory — query LTM then local model",
    "cloud_llm_escalation": "Cloud LLM — escalated to Gemini/OpenAI (last resort)",
}

CHROME_API_DESCRIPTIONS = {
    "prompt": "Prompt API",
    "summarizer": "Summarizer API",
    "translator": "Translator API",
    "language_detector": "Language Detector API",
    "writer": "Writer API",
    "rewriter": "Rewriter API",
    "proofreader": "Proofreader API",
}


def route_task(
    text: str,
    task_type: str,
    is_short: bool,
    is_webpage_grounded: bool,
    is_private: bool,
    requires_action: bool,
    requires_personal_context: bool,
    exceeds_local_limits: bool,
    user_explicit_escalate: bool,
) -> tuple[str, str, str, str]:
    """Route a task and return formatted results for the UI."""
    if not text.strip():
        return "Please enter a task.", "", "", ""

    sensitivity = Sensitivity.SENSITIVE if is_private else Sensitivity.NORMAL
    task = TaskObject(
        text=text,
        task_type=TaskType(task_type.lower()) if task_type.lower() in [t.value for t in TaskType] else TaskType.TRANSFORM,
        is_short=is_short,
        is_webpage_grounded=is_webpage_grounded,
        sensitivity=sensitivity,
        requires_action=requires_action,
        requires_personal_context=requires_personal_context,
        exceeds_local_limits=exceeds_local_limits,
        user_explicit_escalate=user_explicit_escalate,
    )
    ctx = PCOSContext()

    decision = route(task, ctx)

    surface_name = decision.surface if isinstance(decision.surface, str) else decision.surface.value
    surface_desc = SURFACE_DESCRIPTIONS.get(surface_name, surface_name)

    api_name = ""
    if decision.chrome_api:
        api_val = decision.chrome_api if isinstance(decision.chrome_api, str) else decision.chrome_api.value
        api_name = CHROME_API_DESCRIPTIONS.get(api_val, api_val)

    # Build plan
    plan = build_plan(decision, task, ctx)
    plan_json = plan.model_dump_json(indent=2) if hasattr(plan, "model_dump_json") else str(plan)

    result = f"""**Surface:** `{surface_name}`
{surface_desc}

**Chrome API:** {api_name or "N/A"}

**Reason:** {decision.reason}

**Escalate to Cloud:** {"Yes ☁️" if decision.escalate_to_cloud else "No 📱"}

**Latency Target:** {decision.latency_target_ms}ms

**Context Payload:** {len(decision.context_payload)} fields
**Tool Plan:** {len(decision.tool_plan)} steps
"""

    return result, plan_json, surface_name, api_name


def get_health() -> str:
    budgets = {
        "Route": _settings.latency_target_route_ms,
        "Execute": _settings.latency_target_execute_ms,
        "Chrome": _settings.latency_target_chrome_ms,
        "Android": _settings.latency_target_android_ms,
        "Cloud": _settings.latency_target_cloud_ms,
    }
    lines = ["## PCOS Health", "", "| Metric | Budget |", "|---|---|"]
    for k, v in budgets.items():
        lines.append(f"| {k} | {v}ms |")
    lines.append("")
    lines.append(f"**Broker:** {_settings.broker_host}:{_settings.broker_port}")
    lines.append(f"**PiecesOS:** {_settings.piecesos_host}:{_settings.piecesos_port}")
    return "\n".join(lines)


TASK_TYPES = ["Transform", "Generate", "Reasoning", "Action", "Classify"]

with gr.Blocks(
    title="PCOS Context Broker",
    theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="blue"),
) as demo:

    gr.Markdown("# PCOS — Personal Context Operating System")
    gr.Markdown("A local-first hybrid AI runtime. Enter a task below and see how PCOS routes it across Chrome, Android, PiecesOS, and Cloud surfaces.")

    with gr.Row():
        with gr.Column(scale=2):
            task_text = gr.Textbox(
                label="Task",
                placeholder="e.g. 'Summarize this article about quantum computing'",
                lines=3,
            )
            task_type = gr.Dropdown(choices=TASK_TYPES, value="Transform", label="Task Type")

            with gr.Accordion("Task Properties", open=True):
                with gr.Row():
                    is_short = gr.Checkbox(value=True, label="Short (<500 tokens)")
                    is_webpage_grounded = gr.Checkbox(value=False, label="Webpage grounded")
                    is_private = gr.Checkbox(value=False, label="Private/sensitive")

                with gr.Row():
                    requires_action = gr.Checkbox(value=False, label="Requires action")
                    requires_personal_context = gr.Checkbox(value=False, label="Needs personal context")
                    exceeds_local_limits = gr.Checkbox(value=False, label="Exceeds local limits")
                    user_explicit_escalate = gr.Checkbox(value=False, label="User escalate to cloud")

            route_btn = gr.Button("Route Task", variant="primary")

        with gr.Column(scale=3):
            result_md = gr.Markdown(label="Routing Decision")
            with gr.Accordion("Execution Plan (JSON)", open=False):
                plan_json = gr.Code(language="json", label="Plan")

    with gr.Accordion("Health & Latency Budgets", open=False):
        health_md = gr.Markdown(get_health())

    route_btn.click(
        fn=route_task,
        inputs=[task_text, task_type, is_short, is_webpage_grounded, is_private,
                requires_action, requires_personal_context, exceeds_local_limits,
                user_explicit_escalate],
        outputs=[result_md, plan_json, gr.Textbox(visible=False), gr.Textbox(visible=False)],
    )

    # Example tasks
    gr.Examples(
        examples=[
            ["Summarize this article about climate change", "Transform", True, True, False, False, False, False, False],
            ["Translate this page to French", "Transform", True, True, False, False, False, False, False],
            ["What language is this text written in?", "Transform", True, True, False, False, False, False, False],
            ["Proofread my email for grammar", "Transform", True, True, False, False, False, False, False],
            ["Save a note: meeting at 3pm tomorrow", "Action", True, False, False, True, False, False, False],
            ["Write a 50-page research report on AI", "Reasoning", False, False, False, False, False, True, False],
            ["What was I working on last week?", "Transform", True, False, False, False, True, False, False],
        ],
        inputs=[task_text, task_type, is_short, is_webpage_grounded, is_private,
                requires_action, requires_personal_context, exceeds_local_limits,
                user_explicit_escalate],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
