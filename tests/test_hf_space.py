"""Tests for HF Space app functions.

Tests the routing, PII stripping, and metrics functions
used by the Gradio UI without launching the full app.

Run: python -m pytest tests/test_hf_space.py -v
"""
import sys
import os

# Add parent dir to path so hf_space.app can import broker modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hf_space.app import route_task, strip_pii_demo, get_health, get_metrics


class TestRouteTask:
    def test_summarize_routes_to_chrome(self):
        result, plan = route_task(
            "Summarize this article", "Transform", True, True,
            False, False, False, False, False
        )
        assert "chrome_builtin_ai" in result
        assert "Summarizer" in result
        assert plan  # non-empty JSON plan

    def test_translate_routes_to_chrome(self):
        result, _ = route_task(
            "Translate this page to French", "Transform", True, True,
            False, False, False, False, False
        )
        assert "chrome_builtin_ai" in result
        assert "Translator" in result

    def test_action_routes_to_android(self):
        result, _ = route_task(
            "Save a note: meeting at 3pm", "Action", True, False,
            False, True, False, False, False
        )
        assert "android_litert_functiongemma" in result

    def test_long_reasoning_routes_to_cloud(self):
        result, _ = route_task(
            "Write a 50-page research report on AI", "Reasoning", False, False,
            False, False, False, True, False
        )
        assert "cloud_llm_escalation" in result
        assert "Yes" in result

    def test_empty_text_returns_warning(self):
        result, _ = route_task("", "Transform", True, False, False, False, False, False, False)
        assert "enter a task" in result.lower()

    def test_private_routes_to_android(self):
        result, _ = route_task(
            "Analyze my personal health data", "Transform", True, False,
            True, False, False, False, False
        )
        assert "android" in result.lower()

    def test_personal_context_routes_to_piecesos(self):
        result, _ = route_task(
            "What was I working on last week?", "Transform", True, False,
            False, False, True, False, False
        )
        assert "piecesos" in result.lower()


class TestPrivacyInspector:
    def test_email_stripped(self):
        result = strip_pii_demo("Contact john@example.com for info")
        assert "✅" in result
        assert "[EMAIL]" in result or "[email]" in result
        stripped_section = result.split("### Stripped")[1] if "### Stripped" in result else result
        assert "john@example.com" not in stripped_section

    def test_ssn_stripped(self):
        result = strip_pii_demo("My SSN is 123-45-6789")
        assert "✅" in result
        # The stripped section should not contain the SSN
        stripped_section = result.split("### Stripped")[1] if "### Stripped" in result else result
        assert "123-45-6789" not in stripped_section

    def test_no_pii_detected(self):
        result = strip_pii_demo("The weather is nice today")
        assert "No PII detected" in result

    def test_empty_input(self):
        result = strip_pii_demo("")
        assert "enter text" in result.lower() or "enter" in result.lower()


class TestHealth:
    def test_health_returns_markdown(self):
        result = get_health()
        assert "System Health" in result
        assert "Route" in result
        assert "Chrome" in result
        assert "Android" in result
        assert "Cloud" in result
        assert "ms" in result


class TestMetrics:
    def test_metrics_returns_content(self):
        result = get_metrics()
        # Either shows metrics or shows "no requests" message
        assert "Metrics" in result or "metrics" in result.lower()
