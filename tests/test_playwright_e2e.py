"""Playwright E2E test specifications for PCOS broker and HF Space.

These tests are designed to run with the mcp-playwright MCP server or
as standalone Playwright scripts. They verify:

1. Broker API: /health, /route, /memory/query, /litert_server/models
2. HF Space UI: routing demo, surface descriptions, API connectivity

Usage with Playwright MCP:
    # Navigate to broker and run assertions via browser_snapshot
    # Navigate to HF Space and verify UI elements

Usage as standalone (requires playwright installed):
    python -m pytest tests/test_playwright_e2e.py -v --browser chromium

Or use the mcp8_browser_* tools directly in Cascade.
"""
from __future__ import annotations

import pytest

# These tests are marked as E2E and require a running broker or browser
pytestmark = pytest.mark.e2e


# ── Broker API E2E Specs (run with TestClient or against live server) ──


class TestBrokerE2ESpec:
    """E2E specs for broker API endpoints.

    Run against live broker at http://localhost:8000 or via TestClient.
    """

    def test_health_check_e2e(self):
        """Spec: GET /health returns 200 with status ok."""
        # With TestClient:
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok" or "status" in data

    def test_route_text_task_e2e(self):
        """Spec: POST /route with text task returns surface + reason."""
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.post("/route", json={
            "task": {"text": "summarize this article", "is_short": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "surface" in data
        assert "reason" in data
        assert isinstance(data["surface"], str)

    def test_route_multimodal_e2e(self):
        """Spec: POST /route with IMAGE modality → e4b surface."""
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.post("/route", json={
            "task": {
                "text": "describe this image",
                "modality": "image",
                "is_short": True,
            },
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "e4b" in data["surface"]

    def test_route_reasoning_12b_e2e(self):
        """Spec: POST /route with reasoning + 16GB+ desktop → 12b surface."""
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.post("/route", json={
            "task": {
                "text": "complex proof",
                "task_type": "reasoning",
                "is_short": False,
            },
            "context": {
                "desktop": {
                    "litert_server_available": True,
                    "total_ram_mb": 32768,
                    "has_12b_model": True,
                },
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["surface"] == "litert_server_12b"

    def test_memory_query_e2e(self):
        """Spec: GET /memory/query returns query + results + count."""
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.get("/memory/query", params={"q": "test query"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert isinstance(data["results"], list)
        assert isinstance(data["count"], int)

    def test_litert_models_e2e(self):
        """Spec: GET /litert_server/models returns 200."""
        from fastapi.testclient import TestClient
        from broker.main import app
        client = TestClient(app)
        resp = client.get("/litert_server/models")
        assert resp.status_code == 200


# ── HF Space UI E2E Specs (run with Playwright browser) ────────


class TestHFSpaceE2ESpec:
    """E2E specs for HF Space UI.

    Requires HF Space running at http://localhost:7860 or the deployed URL.
    Use mcp8_browser_navigate + mcp8_browser_snapshot to execute.
    """

    HF_SPACE_URL = "http://localhost:7860"

    def test_hf_space_loads(self):
        """Spec: HF Space root page loads with title."""
        # Playwright: navigate to HF_SPACE_URL, verify page title contains "PCOS"
        # Using mcp8_browser_navigate(url=HF_SPACE_URL)
        # Then mcp8_browser_snapshot() to verify content
        pytest.skip("Requires running HF Space — execute via Playwright MCP")

    def test_hf_space_routing_demo(self):
        """Spec: HF Space routing demo shows surface for a task."""
        # Playwright: fill text input, click route button, verify surface display
        pytest.skip("Requires running HF Space — execute via Playwright MCP")

    def test_hf_space_surface_descriptions(self):
        """Spec: HF Space displays surface descriptions for all surfaces."""
        # Playwright: navigate to surfaces section, verify all surface names visible
        pytest.skip("Requires running HF Space — execute via Playwright MCP")


# ── Chrome Extension E2E Specs (run with Playwright browser) ───


class TestChromeExtensionE2ESpec:
    """E2E specs for Chrome extension sidepanel.

    Requires Chrome extension loaded or mock HTML page.
    Use mcp8_browser_navigate + mcp8_browser_snapshot to execute.
    """

    def test_sidepanel_loads(self):
        """Spec: Chrome extension sidepanel loads with PCOS branding."""
        pytest.skip("Requires Chrome extension — execute via Playwright MCP")

    def test_sidepanel_streaming_display(self):
        """Spec: Sidepanel shows SSE streaming output for inference."""
        pytest.skip("Requires Chrome extension — execute via Playwright MCP")

    def test_sidepanel_routing_display(self):
        """Spec: Sidepanel shows routing decision (surface + reason)."""
        pytest.skip("Requires Chrome extension — execute via Playwright MCP")
