"""WebSocket bridge tests — Chrome ↔ Android relay via FastAPI TestClient.

Tests the full WebSocket lifecycle: register, ping/pong, relay between
clients, result delivery, and auth token enforcement.

Run: python -m pytest tests/test_bridge.py -v
"""
import pytest
from fastapi.testclient import TestClient

from broker.main import app
from broker.routers._shared import _bridge_clients


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── Registration ───────────────────────────────────────────────

class TestBridgeRegistration:
    def test_connect_receives_registered(self, client):
        with client.websocket_connect("/bridge") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "registered"
            assert "client_id" in msg

    def test_register_with_role(self, client):
        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()  # initial registered
            ws.send_json({"type": "register", "role": "chrome"})
            msg = ws.receive_json()
            assert msg["type"] == "ack"
            assert msg["role"] == "chrome"
            assert "client_id" in msg

    def test_register_android_role(self, client):
        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()
            ws.send_json({"type": "register", "role": "android"})
            msg = ws.receive_json()
            assert msg["type"] == "ack"
            assert msg["role"] == "android"


# ── Keepalive ─────────────────────────────────────────────────

class TestBridgeKeepalive:
    def test_ping_pong(self, client):
        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()  # registered
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"


# ── Relay between clients ─────────────────────────────────────

class TestBridgeRelay:
    def test_relay_broadcast(self, client):
        """When target is not specified, relay broadcasts to all other clients."""
        with client.websocket_connect("/bridge") as ws1:
            ws1.receive_json()  # registered

            with client.websocket_connect("/bridge") as ws2:
                ws2.receive_json()  # registered

                # ws1 sends a relay message with no target → broadcast
                ws1.send_json({
                    "type": "relay",
                    "payload": {"text": "hello from ws1"},
                })

                msg = ws2.receive_json()
                assert msg["type"] == "relay"
                assert msg["payload"]["text"] == "hello from ws1"
                assert "from" in msg

    def test_relay_targeted(self, client):
        """Relay with a specific target delivers only to that client."""
        with client.websocket_connect("/bridge") as ws1:
            reg1 = ws1.receive_json()
            cid1 = reg1["client_id"]

            with client.websocket_connect("/bridge") as ws2:
                ws2.receive_json()

                # ws2 sends a relay targeting ws1
                ws2.send_json({
                    "type": "relay",
                    "target": cid1,
                    "payload": {"text": "targeted message"},
                })

                msg = ws1.receive_json()
                assert msg["type"] == "relay"
                assert msg["payload"]["text"] == "targeted message"


# ── Result delivery ───────────────────────────────────────────

class TestBridgeResult:
    def test_result_delivery(self, client):
        """Result messages are delivered to the target client."""
        with client.websocket_connect("/bridge") as ws1:
            reg1 = ws1.receive_json()
            cid1 = reg1["client_id"]

            with client.websocket_connect("/bridge") as ws2:
                ws2.receive_json()

                ws2.send_json({
                    "type": "result",
                    "target": cid1,
                    "payload": {"result": "task completed"},
                })

                msg = ws1.receive_json()
                assert msg["type"] == "result"
                assert msg["payload"]["result"] == "task completed"


# ── Auth token ────────────────────────────────────────────────

class TestBridgeAuth:
    def test_invalid_token_rejected(self, client, monkeypatch):
        """When bridge auth token is set, invalid tokens are rejected."""
        from broker.routers import bridge_router
        monkeypatch.setattr(bridge_router, "_BRIDGE_AUTH_TOKEN", "secret-token")

        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()  # registered
            ws.send_json({"type": "register", "role": "chrome", "token": "wrong-token"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "auth" in msg["message"].lower()

    def test_valid_token_accepted(self, client, monkeypatch):
        """When bridge auth token is set, valid tokens are accepted."""
        from broker.routers import bridge_router
        monkeypatch.setattr(bridge_router, "_BRIDGE_AUTH_TOKEN", "secret-token")

        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()
            ws.send_json({"type": "register", "role": "android", "token": "secret-token"})
            msg = ws.receive_json()
            assert msg["type"] == "ack"
            assert msg["role"] == "android"


# ── Cleanup on disconnect ─────────────────────────────────────

class TestBridgeCleanup:
    def test_client_removed_on_disconnect(self, client):
        """Clients are removed from _bridge_clients on disconnect."""
        initial_count = len(_bridge_clients)
        with client.websocket_connect("/bridge") as ws:
            ws.receive_json()
            assert len(_bridge_clients) == initial_count + 1
        # After disconnect, client should be cleaned up
        assert len(_bridge_clients) == initial_count
