"""PCOS HF Space — interactive demo of the Context Broker routing logic.

Tabs:
1. Route Explorer — enter a task, see routing decision + execution plan
2. Privacy Inspector — see PII stripping before/after
3. Cloud Escalation — try cloud LLM escalation with Gemini/OpenAI
4. Metrics Dashboard — local-vs-cloud hit rate, surface breakdown
5. System Health — latency budgets and configuration
"""
from __future__ import annotations

import sys
import os
import asyncio

# Add parent dir to path so we can import broker modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from broker.router.router import route, Surface, ChromeAPI
from broker.planner.planner import build_plan
from broker.context.context_schema import PCOSContext, TaskObject, TaskType, Modality, Sensitivity
from broker.policies.privacy import strip_pii, is_safe_for_cloud, _REPLACEMENTS
from broker.policies.escalation import should_escalate, get_escalation_log, clear_escalation_log
from broker.config import get_settings

_settings = get_settings()

SURFACE_DESCRIPTIONS = {
    "chrome_builtin_ai": "Chrome Built-in AI — runs in browser via LanguageModel/Summarizer/Translator, zero network latency",
    "chrome_webgpu": "Chrome WebGPU — Gemma 4 E2B/E4B runs in browser via LiteRT-LM JS API with WebGPU acceleration",
    "litert_server": "LiteRT-LM Server — local desktop GPU via lit serve (Gemini-compatible API, no cloud)",
    "android_litert_functiongemma": "Android FunctionGemma 270M — on-device function calling, CPU backend",
    "android_litert_gemma_e2b": "Android Gemma 4 E2B (2.3B) — on-device inference, GPU backend with MTP, 2.6GB RAM",
    "android_litert_gemma_e4b": "Android Gemma 4 E4B (4.5B) — on-device full inference, GPU backend with MTP, multimodal, 3.7GB RAM",
    "piecesos_memory_then_local": "PiecesOS Memory — query LTM then local model",
    "cloud_llm_escalation": "Cloud LLM — escalated to Gemini/OpenAI (last resort, PII-stripped)",
}

CHROME_API_DESCRIPTIONS = {
    "prompt": "LanguageModel (Prompt API) — Gemini Nano",
    "summarizer": "Summarizer — summarization with type/length/format",
    "translator": "Translator — expert translation model",
    "language_detector": "LanguageDetector — expert language detection",
    "writer": "Writer — long-form generation (developer trial)",
    "rewriter": "Rewriter — text transformation with tone (developer trial)",
    "proofreader": "Proofreader — grammar/clarity expert (developer trial)",
}

TASK_TYPES = ["Transform", "Action", "Reasoning", "Retrieval"]


# ── Tab 1: Route Explorer ─────────────────────────────────────

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
) -> tuple[str, str]:
    if not text.strip():
        return "Please enter a task.", ""

    sensitivity = Sensitivity.PRIVATE if is_private else Sensitivity.NORMAL
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

    plan = build_plan(decision, task, ctx)
    plan_json = plan.model_dump_json(indent=2) if hasattr(plan, "model_dump_json") else str(plan)

    cloud_icon = "☁️" if decision.escalate_to_cloud else "📱"
    result = f"""## Routing Decision

**Surface:** `{surface_name}`
{surface_desc}

**Chrome API:** {api_name or "N/A"}

**Reason:** {decision.reason}

**Escalate to Cloud:** {"Yes ☁️" if decision.escalate_to_cloud else f"No {cloud_icon}"}

**Latency Target:** {decision.latency_target_ms}ms

**Context Payload:** {len(decision.context_payload)} fields
**Tool Plan:** {len(decision.tool_plan)} steps
"""
    return result, plan_json


# ── Tab 2: Privacy Inspector ──────────────────────────────────

def strip_pii_demo(text: str) -> str:
    if not text.strip():
        return "Enter text with PII to see stripping in action."

    stripped = strip_pii(text)
    safe = is_safe_for_cloud(stripped)

    detections = []
    for pattern, replacement in _REPLACEMENTS:
        matches = pattern.findall(text)
        if matches:
            detections.append(f"- **{replacement}**: {len(matches)} match(es) — {', '.join(str(m) for m in matches[:3])}")

    detections_str = "\n".join(detections) if detections else "- No PII detected"

    result = f"""## PII Stripping Result

**Safe for cloud:** {"✅ Yes" if safe else "❌ No"}

### Detected PII
{detections_str}

### Original ({len(text)} chars)
```
{text}
```

### Stripped ({len(stripped)} chars)
```
{stripped}
```
"""
    return result


# ── Tab 3: Cloud Escalation ───────────────────────────────────

def cloud_escalate(text: str, provider: str) -> str:
    if not text.strip():
        return "Enter a task to escalate to cloud."

    try:
        from models.cloud.escalation_provider import escalate_to_cloud, get_available_providers
        providers = get_available_providers()
        if not providers:
            return """## No Cloud Providers Available

Set one of these environment variables as Space secrets to enable cloud escalation:
- `GEMINI_API_KEY` — Google Gemini (free tier available)
- `OPENAI_API_KEY` — OpenAI

The routing and PII stripping still work — only the actual cloud LLM call requires keys."""

        use_provider = provider if provider in providers else providers[0]

        stripped = strip_pii(text)
        safe = is_safe_for_cloud(stripped)
        if not safe:
            return "## ⚠️ PII Stripping Incomplete\n\nCannot escalate — text still contains detectable PII after stripping."

        result = asyncio.run(escalate_to_cloud(
            task_text=text,
            system_prompt="You are a helpful AI assistant. Provide clear, concise responses.",
            provider=use_provider,
        ))

        return f"""## Cloud Escalation Result

**Provider:** {use_provider}
**PII Stripped:** ✅ Yes

### Response
{result}
"""
    except Exception as e:
        return f"## Error\n\n```\n{e}\n```"


def get_providers_status() -> str:
    try:
        from models.cloud.escalation_provider import get_available_providers
        providers = get_available_providers()
        if not providers:
            return "**Cloud providers:** None configured. Set `GEMINI_API_KEY` or `OPENAI_API_KEY` as Space secrets."
        return f"**Cloud providers available:** {', '.join(providers)}"
    except Exception:
        return "**Cloud providers:** Module not available."


# ── Tab 4: Metrics Dashboard ──────────────────────────────────

def get_metrics() -> str:
    try:
        from broker.routers._shared import get_db

        db = get_db()
        rows = db.execute(
            "SELECT surface, COUNT(*) as count, AVG(latency_ms) as avg_latency, "
            "SUM(local) as local_count, SUM(escalated) as escalated_count "
            "FROM request_metrics GROUP BY surface"
        ).fetchall()

        total = db.execute("SELECT COUNT(*) FROM request_metrics").fetchone()[0]
        total_local = db.execute("SELECT SUM(local) FROM request_metrics").fetchone()[0] or 0
        total_cloud = db.execute("SELECT SUM(escalated) FROM request_metrics").fetchone()[0] or 0

        if total == 0:
            return """## Metrics Dashboard

No requests recorded yet. Use the **Route Explorer** or **Cloud Escalation** tabs to generate traffic."""

        local_rate = round(total_local / total * 100, 1)
        cloud_rate = round(total_cloud / total * 100, 1)

        lines = [
            "## Metrics Dashboard",
            "",
            f"**Total Requests:** {total}",
            f"**Local Hit Rate:** {local_rate}%",
            f"**Cloud Escalation Rate:** {cloud_rate}%",
            "",
            "### By Surface",
            "",
            "| Surface | Count | Avg Latency (ms) | Local | Cloud |",
            "|---------|-------|------------------|-------|-------|",
        ]

        for row in rows:
            surface, count, avg_lat, local, cloud = row
            avg_lat_str = f"{avg_lat:.1f}" if avg_lat else "0"
            lines.append(f"| {surface} | {count} | {avg_lat_str} | {local or 0} | {cloud or 0} |")

        escalations = get_escalation_log()
        if escalations:
            lines.append("")
            lines.append("### Recent Escalations")
            lines.append("")
            for e in escalations[-5:]:
                lines.append(f"- **{e.timestamp[:19]}** — {e.reason} (provider: {e.provider or 'N/A'})")

        return "\n".join(lines)
    except Exception as e:
        return f"## Metrics Error\n\n```\n{e}\n```"


def clear_log() -> str:
    clear_escalation_log()
    return get_metrics()


# ── Tab 5: System Health ──────────────────────────────────────

def get_health() -> str:
    budgets = {
        "Route": _settings.latency_target_route_ms,
        "Execute": _settings.latency_target_execute_ms,
        "Chrome": _settings.latency_target_chrome_ms,
        "Android": _settings.latency_target_android_ms,
        "Cloud": _settings.latency_target_cloud_ms,
    }
    lines = [
        "## System Health",
        "",
        "| Component | Status | Budget |",
        "|-----------|--------|--------|",
        "| Broker | ✅ Running | — |",
    ]
    for k, v in budgets.items():
        lines.append(f"| {k} | ✅ Configured | {v}ms |")
    lines.append("")
    lines.append(f"**PiecesOS:** {_settings.piecesos_host}:{_settings.piecesos_port}")
    lines.append(f"**Bridge Auth:** {'enabled' if _settings.bridge_auth_token else 'disabled'}")
    return "\n".join(lines)


# ── Build UI ──────────────────────────────────────────────────

with gr.Blocks(
    title="PCOS Context Broker",
    theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="blue"),
    css="""
    .gradio-container { max-width: 1200px !important; }
    """,
) as demo:

    gr.Markdown("# PCOS — Personal Context Operating System")
    gr.Markdown("A local-first hybrid AI runtime across Chrome, Android, Pixel Watch, PiecesOS, and cloud LLMs. The intelligence isn't just the LLM — it's the routing.")

    with gr.Tabs():
        # ── Tab 1: Route Explorer ──────────────────────────────
        with gr.Tab("🔍 Route Explorer"):
            gr.Markdown("Enter a task and see how PCOS routes it across surfaces.")
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

            route_btn.click(
                fn=route_task,
                inputs=[task_text, task_type, is_short, is_webpage_grounded, is_private,
                        requires_action, requires_personal_context, exceeds_local_limits,
                        user_explicit_escalate],
                outputs=[result_md, plan_json],
            )

        # ── Tab 2: Privacy Inspector ───────────────────────────
        with gr.Tab("🔒 Privacy Inspector"):
            gr.Markdown("See how PCOS strips PII before sending to cloud. This runs locally — no data leaves your browser.")
            with gr.Row():
                with gr.Column():
                    pii_input = gr.Textbox(
                        label="Text with PII",
                        placeholder="e.g. 'Contact john@example.com or call 555-123-4567. My SSN is 123-45-6789.'",
                        lines=5,
                    )
                    pii_btn = gr.Button("Strip PII", variant="primary")
                with gr.Column():
                    pii_result = gr.Markdown(label="Result")

            pii_btn.click(fn=strip_pii_demo, inputs=[pii_input], outputs=[pii_result])

            gr.Examples(
                examples=[
                    ["Contact john.doe@example.com for details about the project"],
                    ["My phone number is 555-123-4567 and my SSN is 123-45-6789"],
                    ["Server IP is 192.168.1.1, API key: sk-abc123def456ghi789jkl012mno345pqr678"],
                    ["Credit card: 4111 1111 1111 1111, expires 12/25"],
                    ["I live at 123 Main Street, Anytown, CA 90210"],
                ],
                inputs=[pii_input],
            )

        # ── Tab 3: Cloud Escalation ────────────────────────────
        with gr.Tab("☁️ Cloud Escalation"):
            gr.Markdown("Try cloud LLM escalation. PII is stripped before sending. Set `GEMINI_API_KEY` or `OPENAI_API_KEY` as Space secrets to enable.")
            provider_status = gr.Markdown(get_providers_status())

            with gr.Row():
                with gr.Column():
                    cloud_input = gr.Textbox(
                        label="Task to escalate",
                        placeholder="e.g. 'Write a comprehensive analysis of renewable energy trends in 2025'",
                        lines=4,
                    )
                    provider_select = gr.Dropdown(
                        choices=["gemini", "openai"],
                        value="gemini",
                        label="Cloud Provider",
                    )
                    cloud_btn = gr.Button("Escalate to Cloud", variant="primary")
                with gr.Column():
                    cloud_result = gr.Markdown(label="Result")

            cloud_btn.click(fn=cloud_escalate, inputs=[cloud_input, provider_select], outputs=[cloud_result])

            gr.Examples(
                examples=[
                    ["Explain quantum entanglement in simple terms", "gemini"],
                    ["Write a short poem about artificial intelligence", "gemini"],
                    ["Summarize the key points of the Paris Climate Agreement", "openai"],
                ],
                inputs=[cloud_input, provider_select],
            )

        # ── Tab 4: Metrics Dashboard ───────────────────────────
        with gr.Tab("📊 Metrics"):
            with gr.Row():
                metrics_btn = gr.Button("Refresh Metrics", variant="primary")
                clear_btn = gr.Button("Clear Escalation Log", variant="stop")

            metrics_md = gr.Markdown(get_metrics())

            metrics_btn.click(fn=get_metrics, outputs=[metrics_md])
            clear_btn.click(fn=clear_log, outputs=[metrics_md])

        # ── Tab 5: System Health ───────────────────────────────
        with gr.Tab("🏥 Health"):
            health_md = gr.Markdown(get_health())
            refresh_health = gr.Button("Refresh")
            refresh_health.click(fn=get_health, outputs=[health_md])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
