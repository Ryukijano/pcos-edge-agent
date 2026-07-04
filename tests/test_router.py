"""PCOS routing table tests — covers every branch of the routing decision tree.

Run: python -m pytest tests/test_router.py -v
"""
import pytest
from broker.context.context_schema import (
    TaskObject, PCOSContext, BrowserContext, AndroidContext,
    Modality, Sensitivity, TaskType, NetworkType,
)
from broker.router.router import route, Surface, ChromeAPI
from broker.policies.privacy import strip_pii, is_safe_for_cloud


# ── Helper ─────────────────────────────────────────────────────

def _task(**kwargs) -> TaskObject:
    defaults = {"text": "test task"}
    defaults.update(kwargs)
    return TaskObject(**defaults)


# ── Routing decision tree tests ────────────────────────────────

class TestPrivateOffline:
    def test_private_task_routes_to_android(self):
        t = _task(sensitivity=Sensitivity.PRIVATE)
        d = route(t)
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.ANDROID_GEMMA_E4B)
        assert "Private" in d.reason or "offline" in d.reason
        assert not d.escalate_to_cloud

    def test_offline_context_routes_to_android(self):
        t = _task()
        ctx = PCOSContext(android=AndroidContext(network_type=NetworkType.OFFLINE))
        d = route(t, ctx)
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.ANDROID_GEMMA_E4B)
        assert not d.escalate_to_cloud


class TestMultimodal:
    def test_image_non_web_routes_to_android(self):
        t = _task(modality=Modality.IMAGE, is_webpage_grounded=False)
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_audio_non_web_routes_to_android(self):
        t = _task(modality=Modality.AUDIO, is_webpage_grounded=False)
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E4B


class TestChromeBuiltinAI:
    def test_summarize_routes_to_summarizer(self):
        t = _task(text="summarize this article", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.SUMMARIZER

    def test_rewrite_routes_to_rewriter(self):
        t = _task(text="rewrite this paragraph", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.REWRITER

    def test_translate_routes_to_translator(self):
        t = _task(text="translate this to French", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.TRANSLATOR

    def test_detect_language_routes_to_detector(self):
        t = _task(text="detect language of this text", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.LANGUAGE_DETECTOR

    def test_proofread_routes_to_proofreader(self):
        t = _task(text="proofread this text", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.PROOFREADER

    def test_write_routes_to_writer(self):
        t = _task(text="write a draft email", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.WRITER

    def test_default_transform_routes_to_prompt(self):
        t = _task(text="explain this paragraph", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.PROMPT

    def test_long_transform_not_chrome(self):
        t = _task(text="summarize this", is_webpage_grounded=True, is_short=False, task_type=TaskType.TRANSFORM)
        d = route(t)
        assert d.surface != Surface.CHROME_BUILTIN_AI


class TestPiecesOSMemory:
    def test_personal_context_routes_to_piecesos(self):
        t = _task(requires_personal_context=True)
        d = route(t)
        assert d.surface == Surface.PIECESOS_MEMORY
        assert any(step.get("step") == "query_piecesos" for step in d.tool_plan)


class TestFunctionGemma:
    def test_action_routes_to_functiongemma(self):
        t = _task(requires_action=True)
        d = route(t)
        assert d.surface == Surface.ANDROID_FUNCTION_GEMMA
        assert any(step.get("step") == "function_call" for step in d.tool_plan)


class TestCloudEscalation:
    def test_explicit_escalation_routes_to_cloud(self):
        t = _task(user_explicit_escalate=True)
        d = route(t)
        assert d.surface == Surface.CLOUD_LLM
        assert d.escalate_to_cloud
        assert "explicitly" in d.reason

    def test_long_reasoning_routes_to_cloud(self):
        t = _task(task_type=TaskType.REASONING, is_short=False)
        d = route(t)
        assert d.surface == Surface.CLOUD_LLM
        assert d.escalate_to_cloud

    def test_exceeds_local_limits_routes_to_cloud(self):
        t = _task(exceeds_local_limits=True)
        d = route(t)
        assert d.surface == Surface.CLOUD_LLM
        assert d.escalate_to_cloud

    def test_cloud_payload_is_pii_stripped(self):
        t = _task(text="email me at john@example.com about this", exceeds_local_limits=True)
        d = route(t)
        assert d.context_payload.get("stripped") is True
        assert "john@example.com" not in d.context_payload.get("task_text", "")


class TestDefault:
    def test_default_webpage_grounded_routes_to_chrome(self):
        t = _task(text="what is this page about", is_webpage_grounded=True, is_short=True)
        d = route(t)
        assert d.surface == Surface.CHROME_BUILTIN_AI
        assert d.chrome_api == ChromeAPI.PROMPT

    def test_default_non_webpage_routes_to_android_gemma(self):
        t = _task(text="tell me a joke")
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E2B


# ── Privacy policy tests ───────────────────────────────────────

class TestPrivacy:
    def test_strip_email(self):
        assert "john@example.com" not in strip_pii("contact john@example.com")
        assert "[EMAIL]" in strip_pii("contact john@example.com")

    def test_strip_phone(self):
        assert "555-123-4567" not in strip_pii("call 555-123-4567")
        assert "[PHONE]" in strip_pii("call 555-123-4567")

    def test_strip_ip(self):
        assert "192.168.1.1" not in strip_pii("server at 192.168.1.1")
        assert "[IP]" in strip_pii("server at 192.168.1.1")

    def test_strip_api_key(self):
        assert "sk-abc123def456ghi789jkl012mno345pqr678" not in strip_pii("key: sk-abc123def456ghi789jkl012mno345pqr678")
        assert "[API_KEY]" in strip_pii("key: sk-abc123def456ghi789jkl012mno345pqr678")

    def test_strip_credit_card(self):
        assert "4111 1111 1111 1111" not in strip_pii("card: 4111 1111 1111 1111")
        assert "[CARD]" in strip_pii("card: 4111 1111 1111 1111")

    def test_strip_ssn(self):
        assert "123-45-6789" not in strip_pii("ssn: 123-45-6789")
        assert "[SSN]" in strip_pii("ssn: 123-45-6789")

    def test_strip_address(self):
        assert "123 Main Street" not in strip_pii("live at 123 Main Street")
        assert "[ADDRESS]" in strip_pii("live at 123 Main Street")

    def test_is_safe_for_cloud_clean(self):
        assert is_safe_for_cloud("hello world") is True

    def test_is_safe_for_cloud_with_email(self):
        assert is_safe_for_cloud("contact john@example.com") is False

    def test_is_safe_after_stripping(self):
        stripped = strip_pii("contact john@example.com")
        assert is_safe_for_cloud(stripped) is True


# ── Context schema tests ───────────────────────────────────────

class TestContextSchema:
    def test_prompt_prefix_includes_browser(self):
        ctx = PCOSContext(browser=BrowserContext(url="https://example.com", page_title="Example"))
        prefix = ctx.to_prompt_prefix()
        assert "Example" in prefix
        assert "https://example.com" in prefix

    def test_prompt_prefix_truncation(self):
        ctx = PCOSContext(browser=BrowserContext(selection="x" * 5000))
        prefix = ctx.to_prompt_prefix(max_chars=100)
        assert len(prefix) <= 100

    def test_is_offline(self):
        ctx = PCOSContext(android=AndroidContext(network_type=NetworkType.OFFLINE))
        assert ctx.is_offline() is True

    def test_is_not_offline(self):
        ctx = PCOSContext(android=AndroidContext(network_type=NetworkType.WIFI))
        assert ctx.is_offline() is False


# ── Planner tests ──────────────────────────────────────────────

class TestPlanner:
    def test_plan_has_system_prompt(self):
        from broker.planner.planner import build_plan
        t = _task(text="summarize this", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        plan = build_plan(d, t)
        assert plan.system_prompt != ""
        assert plan.surface == Surface.CHROME_BUILTIN_AI.value

    def test_plan_has_tools_for_action(self):
        from broker.planner.planner import build_plan, FUNCTIONGEMMA_TOOLS
        t = _task(requires_action=True)
        d = route(t)
        plan = build_plan(d, t)
        assert len(plan.tools) == len(FUNCTIONGEMMA_TOOLS)
        assert plan.tools[0]["name"] == "save_note"

    def test_plan_has_chrome_api_params(self):
        from broker.planner.planner import build_plan
        t = _task(text="summarize this", is_webpage_grounded=True, is_short=True, task_type=TaskType.TRANSFORM)
        d = route(t)
        plan = build_plan(d, t)
        assert plan.chrome_api == "summarizer"
        assert "type" in plan.chrome_api_params
