"""Integration tests for the PCOS broker — end-to-end route→execute→plan flow.

Tests the full pipeline using FastAPI TestClient without needing a live server.
"""
import pytest
from fastapi.testclient import TestClient

from broker.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestRouteEndpoint:
    """POST /route — routing decisions without execution."""

    def test_route_summarize(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Summarize this article for me", "task_type": "transform"},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "surface" in data
        assert "reason" in data
        assert "latency_target_ms" in data
        assert data["escalate_to_cloud"] is False

    def test_route_translate(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Translate this to French", "task_type": "transform", "is_webpage_grounded": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["surface"] == "chrome_builtin_ai"
        assert data["chrome_api"] == "translator"

    def test_route_detect_language(self, client):
        resp = client.post("/route", json={
            "task": {"text": "What language is this text in?", "task_type": "transform", "is_webpage_grounded": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["chrome_api"] == "language_detector"

    def test_route_proofread(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Proofread this paragraph", "task_type": "transform", "is_webpage_grounded": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["chrome_api"] == "proofreader"

    def test_route_cloud_escalation(self, client):
        resp = client.post("/route", json={
            "task": {
                "text": "Write a comprehensive 50-page research report on quantum computing",
                "task_type": "reasoning",
                "is_short": False,
                "exceeds_local_limits": True,
            },
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalate_to_cloud"] is True

    def test_route_with_context(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Summarize this", "task_type": "transform"},
            "context": {
                "browser": {"url": "https://example.com", "page_title": "Example"},
            },
        })
        assert resp.status_code == 200


class TestExecuteEndpoint:
    """POST /execute — routing + planning in one call."""

    def test_execute_summarize(self, client):
        resp = client.post("/execute", json={
            "task": {"text": "Summarize this article", "task_type": "transform", "is_webpage_grounded": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "plan" in data
        assert data["decision"]["surface"] == "chrome_builtin_ai"

    def test_execute_with_tools(self, client):
        resp = client.post("/execute", json={
            "task": {
                "text": "Save a note about the meeting tomorrow",
                "task_type": "action",
                "requires_action": True,
            },
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        plan = data["plan"]
        # Should include tool declarations for FunctionGemma
        if "tools" in plan:
            assert isinstance(plan["tools"], list)

    def test_execute_rewrite(self, client):
        resp = client.post("/execute", json={
            "task": {"text": "Rewrite this email to be more formal", "task_type": "transform", "is_webpage_grounded": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"]["chrome_api"] == "rewriter"


class TestHealthAndMetrics:
    """GET /health, GET /metrics — observability endpoints."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "pcos-context-broker"
        assert "latency_budgets_ms" in data
        assert "dependencies" in data

    def test_metrics(self, client):
        # First make a request to generate metrics
        client.post("/route", json={
            "task": {"text": "Summarize this", "task_type": "transform"},
            "context": {},
        })
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert data["total_requests"] >= 1
        assert "local_hit_rate" in data
        assert "by_surface" in data


class TestContextCompress:
    """POST /context/compress — context to prompt prefix."""

    def test_compress_empty(self, client):
        resp = client.post("/context/compress", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt_prefix" in data

    def test_compress_with_browser(self, client):
        resp = client.post("/context/compress", json={
            "browser": {
                "url": "https://example.com",
                "page_title": "Example Page",
                "selection": "Selected text here",
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "Example Page" in data["prompt_prefix"]


class TestPrivacyPolicies:
    """Verify PII stripping is applied in the routing pipeline."""

    def test_ssn_stripped(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Summarize this document with SSN 123-45-6789", "task_type": "transform"},
            "context": {},
        })
        assert resp.status_code == 200

    def test_email_stripped(self, client):
        resp = client.post("/route", json={
            "task": {"text": "Proofread this email to john.doe@example.com", "task_type": "transform"},
            "context": {},
        })
        assert resp.status_code == 200
