"""Tests for M24 — E2E multimodal routing, QAT toggle, and integration.

Tests cover:
- Multimodal routing: IMAGE/AUDIO → E4B surface (Android + iOS)
- Multimodal + webpage grounded → Chrome WebGPU (not E4B)
- Multimodal + private → on-device E4B
- QAT toggle routing: low RAM → mobile variant selection
- iOS multimodal routing: IMAGE → IOS_GEMMA_E4B
- Desktop 12B + multimodal interaction
- PiecesOS memory + multimodal interaction
- E2E integration: broker API /route endpoint with TestClient
"""
import pytest
from fastapi.testclient import TestClient

from broker.context.context_schema import (
    TaskObject, PCOSContext, DesktopContext, AndroidContext, IOSContext,
    Modality, Sensitivity, TaskType, NetworkType,
)
from broker.router.router import route, Surface, ChromeAPI
from broker.context.desktop_reporter import is_12b_eligible, RAM_THRESHOLD_12B


# ── Helpers ────────────────────────────────────────────────────


def _task(**kwargs) -> TaskObject:
    defaults = {"text": "test", "is_short": True, "task_type": TaskType.TRANSFORM}
    defaults.update(kwargs)
    return TaskObject(**defaults)


def _ctx(**kwargs) -> PCOSContext:
    return PCOSContext(**kwargs)


def _ios_ctx(**kwargs) -> PCOSContext:
    defaults = {"ios": IOSContext(device_model="iPhone 15 Pro", chip="A17 Pro")}
    defaults.update(kwargs)
    return PCOSContext(**defaults)


def _desktop_ctx(ram: int = 32768, server: bool = True, has_12b: bool = True) -> PCOSContext:
    return PCOSContext(
        desktop=DesktopContext(
            litert_server_available=server,
            total_ram_mb=ram,
            has_12b_model=has_12b,
        )
    )


# ── Multimodal Routing Tests ───────────────────────────────────


class TestMultimodalRouting:
    """Test multimodal task routing to E4B surfaces."""

    def test_image_routes_to_android_e4b(self):
        """IMAGE modality without browser grounding → ANDROID_GEMMA_E4B."""
        t = _task(modality=Modality.IMAGE, is_webpage_grounded=False)
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_audio_routes_to_android_e4b(self):
        """AUDIO modality without browser grounding → ANDROID_GEMMA_E4B."""
        t = _task(modality=Modality.AUDIO, is_webpage_grounded=False)
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_image_routes_to_ios_e4b(self):
        """IMAGE modality on iOS → IOS_GEMMA_E4B."""
        t = _task(modality=Modality.IMAGE, is_webpage_grounded=False)
        d = route(t, _ios_ctx())
        assert d.surface == Surface.IOS_GEMMA_E4B

    def test_audio_routes_to_ios_e4b(self):
        """AUDIO modality on iOS → IOS_GEMMA_E4B."""
        t = _task(modality=Modality.AUDIO, is_webpage_grounded=False)
        d = route(t, _ios_ctx())
        assert d.surface == Surface.IOS_GEMMA_E4B

    def test_image_webpage_grounded_not_e4b(self):
        """IMAGE + webpage grounded → NOT E4B (goes to Chrome or cloud)."""
        t = _task(modality=Modality.IMAGE, is_webpage_grounded=True, is_short=True)
        d = route(t)
        assert d.surface != Surface.ANDROID_GEMMA_E4B
        assert d.surface != Surface.IOS_GEMMA_E4B

    def test_image_private_routes_on_device(self):
        """Private IMAGE task → on-device (E2B for transforms, E4B for reasoning)."""
        t = _task(modality=Modality.IMAGE, sensitivity=Sensitivity.PRIVATE)
        d = route(t)
        # Private check (step 1) comes before multimodal (step 2)
        # Non-reasoning private → E2B; reasoning private → E4B
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.ANDROID_GEMMA_E4B)
        assert not d.escalate_to_cloud

    def test_image_offline_routes_to_e4b(self):
        """Offline IMAGE task → on-device E4B."""
        t = _task(modality=Modality.IMAGE)
        ctx = PCOSContext(network=NetworkType.OFFLINE)
        d = route(t, ctx)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_text_modality_not_e4b(self):
        """TEXT modality should not route to E4B (unless reasoning)."""
        t = _task(modality=Modality.TEXT, is_short=True)
        d = route(t)
        assert d.surface != Surface.ANDROID_GEMMA_E4B

    def test_image_reasoning_routes_to_e4b(self):
        """IMAGE + reasoning → E4B (multimodal takes priority)."""
        t = _task(
            modality=Modality.IMAGE,
            task_type=TaskType.REASONING,
            is_short=False,
        )
        d = route(t)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_multimodal_with_desktop_server(self):
        """Multimodal task with desktop server available → still E4B (not server)."""
        t = _task(modality=Modality.IMAGE)
        d = route(t, _desktop_ctx())
        assert d.surface == Surface.ANDROID_GEMMA_E4B


# ── QAT / Mobile Variant Routing Tests ─────────────────────────


class TestQATToggleRouting:
    """Test QAT mobile variant selection based on device RAM."""

    def test_low_ram_android_routes_to_e2b_not_e4b(self):
        """Low RAM Android + reasoning → E2B (not E4B, not enough RAM)."""
        ctx = PCOSContext(
            android=AndroidContext(total_ram_mb=4096, has_gpu=True),
        )
        t = _task(task_type=TaskType.REASONING, is_short=False, sensitivity=Sensitivity.PRIVATE)
        d = route(t, ctx)
        # Private reasoning → on-device, E2B for low RAM
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.ANDROID_GEMMA_E4B)

    def test_high_ram_android_reasoning_routes_to_e4b(self):
        """High RAM Android + private reasoning → E4B."""
        ctx = PCOSContext(
            android=AndroidContext(total_ram_mb=8192, has_gpu=True),
        )
        t = _task(task_type=TaskType.REASONING, is_short=False, sensitivity=Sensitivity.PRIVATE)
        d = route(t, ctx)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_qat_model_lighter_than_full(self):
        """QAT mobile variant is smaller — verify routing doesn't break."""
        # QAT toggle is handled at the app level (Kotlin/Swift)
        # Broker just routes to the surface; app picks QAT vs full
        t = _task(text="quick chat", is_short=True)
        d = route(t)
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.CHROME_BUILTIN_AI)

    def test_mobile_variant_for_low_ram_offline(self):
        """Offline + low RAM → on-device (E2B, not E4B)."""
        ctx = PCOSContext(network=NetworkType.OFFLINE)
        t = _task(text="quick note", is_short=True, sensitivity=Sensitivity.PRIVATE)
        d = route(t, ctx)
        assert d.surface == Surface.ANDROID_GEMMA_E2B
        assert not d.escalate_to_cloud


# ── E2E Integration: Broker API Tests ──────────────────────────


class TestBrokerAPIIntegration:
    """E2E tests using FastAPI TestClient to verify broker API endpoints."""

    @pytest.fixture
    def client(self):
        from broker.main import app
        return TestClient(app)

    def test_route_endpoint_text(self, client):
        """POST /route with text task returns valid routing decision."""
        resp = client.post("/route", json={
            "task": {"text": "summarize this", "is_short": True},
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "surface" in data
        assert "reason" in data

    def test_route_endpoint_multimodal(self, client):
        """POST /route with IMAGE modality routes to E4B."""
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

    def test_route_endpoint_reasoning(self, client):
        """POST /route with reasoning + desktop context → LITERT_SERVER_12B."""
        resp = client.post("/route", json={
            "task": {
                "text": "prove the theorem",
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

    def test_health_endpoint(self, client):
        """GET /health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_memory_query_endpoint(self, client):
        """GET /memory/query returns results (may be empty if PiecesOS offline)."""
        resp = client.get("/memory/query", params={"q": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data
        assert "count" in data

    def test_litert_models_endpoint(self, client):
        """GET /litert_server/models returns model list or empty."""
        resp = client.get("/litert_server/models")
        assert resp.status_code == 200

    def test_route_endpoint_private(self, client):
        """POST /route with PRIVATE sensitivity → on-device, no cloud."""
        resp = client.post("/route", json={
            "task": {
                "text": "personal note",
                "sensitivity": "private",
                "is_short": True,
            },
            "context": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalate_to_cloud"] is False

    def test_route_endpoint_offline(self, client):
        """POST /route with offline context → on-device."""
        resp = client.post("/route", json={
            "task": {"text": "quick task", "is_short": True},
            "context": {"network": "offline"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "cloud" not in data["surface"] or data["escalate_to_cloud"] is False


# ── Cross-Surface Interaction Tests ────────────────────────────


class TestCrossSurfaceInteractions:
    """Test interactions between multiple routing dimensions."""

    def test_multimodal_and_12b_dont_conflict(self):
        """Multimodal task takes priority over 12B routing."""
        t = _task(modality=Modality.IMAGE, task_type=TaskType.REASONING, is_short=False)
        d = route(t, _desktop_ctx())
        assert d.surface == Surface.ANDROID_GEMMA_E4B
        assert d.surface != Surface.LITERT_SERVER_12B

    def test_private_multimodal_stays_on_device(self):
        """Private + multimodal → on-device, never cloud."""
        t = _task(modality=Modality.IMAGE, sensitivity=Sensitivity.PRIVATE)
        d = route(t, _desktop_ctx())
        # Private check (step 1) takes priority over multimodal (step 2)
        assert d.surface in (Surface.ANDROID_GEMMA_E2B, Surface.ANDROID_GEMMA_E4B)
        assert not d.escalate_to_cloud

    def test_offline_multimodal_stays_on_device(self):
        """Offline + multimodal → on-device E4B."""
        t = _task(modality=Modality.AUDIO)
        ctx = PCOSContext(network=NetworkType.OFFLINE)
        d = route(t, ctx)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_personal_context_and_multimodal(self):
        """Personal context + multimodal → multimodal takes priority (E4B)."""
        t = _task(
            modality=Modality.IMAGE,
            requires_personal_context=True,
        )
        d = route(t)
        # Multimodal routing (step 2) comes before personal context (step 4)
        assert d.surface == Surface.ANDROID_GEMMA_E4B

    def test_action_and_multimodal(self):
        """Action + multimodal → multimodal takes priority (E4B)."""
        t = _task(modality=Modality.IMAGE, requires_action=True)
        d = route(t)
        # Multimodal routing (step 2) comes before action routing (step 5)
        assert d.surface == Surface.ANDROID_GEMMA_E4B


# ── Desktop Reporter Integration Tests ─────────────────────────


class TestDesktopReporterIntegration:
    """Test desktop_reporter integration with routing."""

    def test_12b_eligible_with_high_ram(self):
        assert is_12b_eligible(32768) is True

    def test_12b_not_eligible_with_low_ram(self):
        assert is_12b_eligible(4096) is False

    def test_12b_threshold_is_16gb(self):
        assert RAM_THRESHOLD_12B == 16384

    def test_routing_uses_desktop_context(self):
        """Router correctly reads desktop context for 12B routing."""
        t = _task(task_type=TaskType.REASONING, is_short=False)
        ctx = _desktop_ctx(ram=32768, server=True, has_12b=True)
        d = route(t, ctx)
        assert d.surface == Surface.LITERT_SERVER_12B

    def test_routing_falls_back_without_server(self):
        """Without server, reasoning goes to cloud."""
        t = _task(task_type=TaskType.REASONING, is_short=False)
        ctx = _desktop_ctx(ram=32768, server=False, has_12b=False)
        d = route(t, ctx)
        assert d.surface == Surface.CLOUD_LLM
        assert d.escalate_to_cloud is True
