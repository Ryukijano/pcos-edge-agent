"""Tests for M21 — Desktop 12B routing and context reporter.

Tests cover:
- 12B routing decision (RAM ≥ 16384 + REASONING → LITERT_SERVER_12B)
- 12B routing fallback (RAM < 16384 → LITERT_SERVER, not 12B)
- No server available → CLOUD_LLM
- desktop_reporter: detect_desktop_context with mocked HTTP
- desktop_reporter: is_12b_eligible threshold
- setup_litert_server: model selection logic
"""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from broker.context.context_schema import (
    PCOSContext, DesktopContext, TaskObject, TaskType, Modality, Sensitivity,
)
from broker.router.router import route, Surface
from broker.context.desktop_reporter import (
    detect_desktop_context,
    detect_desktop_context_sync,
    is_12b_eligible,
    RAM_THRESHOLD_12B,
)


# ── 12B Routing Decision Tests ─────────────────────────────────


class TestRouting12B:
    """Test that the router correctly selects LITERT_SERVER_12B vs LITERT_SERVER."""

    def _make_reasoning_task(self, text: str = "Prove the Riemann hypothesis") -> TaskObject:
        return TaskObject(
            text=text,
            task_type=TaskType.REASONING,
            is_short=False,
        )

    def test_12b_routing_high_ram_reasoning(self):
        """RAM >= 16384 + REASONING + server available → LITERT_SERVER_12B."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=32768,
                has_12b_model=True,
            ),
        )
        task = self._make_reasoning_task()
        decision = route(task, ctx)
        assert decision.surface == Surface.LITERT_SERVER_12B
        assert "12B" in decision.reason or "12b" in decision.reason

    def test_12b_routing_exactly_16gb(self):
        """RAM == 16384 (exactly 16GB) + REASONING → LITERT_SERVER_12B."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=16384,
            ),
        )
        task = self._make_reasoning_task()
        decision = route(task, ctx)
        assert decision.surface == Surface.LITERT_SERVER_12B

    def test_12b_routing_low_ram_falls_back(self):
        """RAM < 16384 + REASONING → LITERT_SERVER (not 12B)."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=8192,
            ),
        )
        task = self._make_reasoning_task()
        decision = route(task, ctx)
        assert decision.surface == Surface.LITERT_SERVER
        assert decision.surface != Surface.LITERT_SERVER_12B

    def test_12b_routing_no_server_falls_to_cloud(self):
        """No server available + REASONING → CLOUD_LLM."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=False,
                total_ram_mb=32768,
            ),
        )
        task = self._make_reasoning_task()
        decision = route(task, ctx)
        assert decision.surface == Surface.CLOUD_LLM
        assert decision.escalate_to_cloud is True

    def test_12b_routing_not_reasoning_uses_standard_server(self):
        """Non-reasoning long task + server available → LITERT_SERVER (not 12B)."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=32768,
            ),
        )
        task = TaskObject(
            text="Summarize this very long document…",
            task_type=TaskType.TRANSFORM,
            is_short=False,
            exceeds_local_limits=True,
        )
        decision = route(task, ctx)
        assert decision.surface == Surface.LITERT_SERVER
        assert decision.surface != Surface.LITERT_SERVER_12B

    def test_12b_routing_high_ram_but_short_task_uses_default(self):
        """Short reasoning task → not routed to 12B (stays on device)."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=32768,
            ),
        )
        task = TaskObject(
            text="What is 2+2?",
            task_type=TaskType.REASONING,
            is_short=True,
        )
        decision = route(task, ctx)
        # Short reasoning goes to default (Android E4B), not 12B server
        assert decision.surface != Surface.LITERT_SERVER_12B

    def test_12b_routing_zero_ram_treated_as_low(self):
        """RAM == 0 (uninitialised) + REASONING → LITERT_SERVER (not 12B)."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=0,
            ),
        )
        task = self._make_reasoning_task()
        decision = route(task, ctx)
        assert decision.surface == Surface.LITERT_SERVER


# ── Desktop Reporter Tests ─────────────────────────────────────


class TestDesktopReporter:
    """Test desktop_reporter module."""

    @pytest.mark.asyncio
    @patch("broker.context.desktop_reporter.httpx.AsyncClient")
    async def test_detect_desktop_context_server_available(self, mock_client_cls):
        """When lit serve is running, detect available + 12B model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gemma4-e2b"},
                {"id": "gemma4-e4b"},
                {"id": "gemma4-12b"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await detect_desktop_context()
        assert result["litert_server_available"] is True
        assert result["has_12b_model"] is True
        assert result["total_ram_mb"] > 0

    @pytest.mark.asyncio
    @patch("broker.context.desktop_reporter.httpx.AsyncClient")
    async def test_detect_desktop_context_server_unavailable(self, mock_client_cls):
        """When lit serve is not running, detect unavailable."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await detect_desktop_context()
        assert result["litert_server_available"] is False
        assert result["has_12b_model"] is False
        assert result["total_ram_mb"] > 0

    @pytest.mark.asyncio
    @patch("broker.context.desktop_reporter.httpx.AsyncClient")
    async def test_detect_desktop_context_no_12b_model(self, mock_client_cls):
        """When server has only small models, has_12b_model is False."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gemma4-e2b"},
                {"id": "gemma4-e4b"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await detect_desktop_context()
        assert result["litert_server_available"] is True
        assert result["has_12b_model"] is False

    @patch("broker.context.desktop_reporter.httpx.get")
    def test_detect_sync_server_available(self, mock_get):
        """Sync version detects server correctly."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"data": [{"id": "gemma4-12b"}]}),
        )
        result = detect_desktop_context_sync()
        assert result["litert_server_available"] is True
        assert result["has_12b_model"] is True

    @patch("broker.context.desktop_reporter.httpx.get")
    def test_detect_sync_server_unavailable(self, mock_get):
        """Sync version handles connection failure."""
        mock_get.side_effect = Exception("Connection refused")
        result = detect_desktop_context_sync()
        assert result["litert_server_available"] is False
        assert result["has_12b_model"] is False

    def test_is_12b_eligible_high_ram(self):
        """is_12b_eligible returns True for 16GB+."""
        assert is_12b_eligible(16384) is True
        assert is_12b_eligible(32768) is True

    def test_is_12b_eligible_low_ram(self):
        """is_12b_eligible returns False for < 16GB."""
        assert is_12b_eligible(8192) is False
        assert is_12b_eligible(0) is False
        assert is_12b_eligible(16383) is False

    def test_ram_threshold_constant(self):
        """RAM_THRESHOLD_12B is 16384 (16GB)."""
        assert RAM_THRESHOLD_12B == 16384


# ── DesktopContext Schema Tests ────────────────────────────────


class TestDesktopContextSchema:
    """Test DesktopContext pydantic model fields."""

    def test_defaults(self):
        ctx = DesktopContext()
        assert ctx.litert_server_available is False
        assert ctx.litert_server_url == "http://localhost:9379"
        assert ctx.has_gpu is False
        assert ctx.total_ram_mb == 0
        assert ctx.has_12b_model is False

    def test_with_values(self):
        ctx = DesktopContext(
            litert_server_available=True,
            total_ram_mb=32768,
            has_12b_model=True,
            has_gpu=True,
            gpu_name="NVIDIA RTX 4090",
            os_type="linux",
        )
        assert ctx.litert_server_available is True
        assert ctx.total_ram_mb == 32768
        assert ctx.has_12b_model is True
        assert ctx.gpu_name == "NVIDIA RTX 4090"

    def test_in_pcos_context(self):
        """DesktopContext is accessible via PCOSContext.desktop."""
        ctx = PCOSContext(
            desktop=DesktopContext(
                litert_server_available=True,
                total_ram_mb=16384,
            )
        )
        assert ctx.desktop.litert_server_available is True
        assert ctx.desktop.total_ram_mb == 16384


# ── Config Tests ───────────────────────────────────────────────


class TestConfigLiteRTServer:
    """Test that config has LiteRT server settings."""

    def test_litert_server_url_default(self):
        from broker.config import Settings
        s = Settings()
        assert s.litert_server_url == "http://localhost:9379"

    def test_litert_server_12b_model_id_default(self):
        from broker.config import Settings
        s = Settings()
        assert s.litert_server_12b_model_id == "gemma4-12b"

    def test_litert_server_default_model_id(self):
        from broker.config import Settings
        s = Settings()
        assert s.litert_server_default_model_id == "gemma4-e2b"

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("PCOS_LITERT_SERVER_URL", "http://192.168.1.100:9379")
        from broker.config import Settings
        s = Settings()
        assert s.litert_server_url == "http://192.168.1.100:9379"
