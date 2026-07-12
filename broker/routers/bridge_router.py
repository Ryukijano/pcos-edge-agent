"""WebSocket bridge router for Chrome ↔ Android relay."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from broker.config import get_settings
from broker.logging import get_logger
from broker.routers._shared import _bridge_clients

router = APIRouter(tags=["bridge"])
_settings = get_settings()
_log = get_logger("broker.bridge")

_BRIDGE_AUTH_TOKEN = _settings.bridge_auth_token
_BRIDGE_AUTH_REQUIRED = _settings.bridge_auth_required


@router.websocket("/bridge")
async def bridge(ws: WebSocket):
    """Relay hub for Chrome extension ↔ Android app communication.

    Message format: {"type": "register"|"relay"|"result", "client_id": "...", "target": "...", "payload": {...}}

    If PCOS_BRIDGE_TOKEN env var is set, clients must include it in their
    first register message as {"token": "..."}.
    """
    await ws.accept()
    client_id = str(uuid.uuid4())
    _bridge_clients[client_id] = ws
    await ws.send_json({"type": "registered", "client_id": client_id})

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type", "")

            if msg_type == "register":
                role = msg.get("role", "unknown")

                if _BRIDGE_AUTH_REQUIRED and not _BRIDGE_AUTH_TOKEN:
                    await ws.send_json({"type": "error", "message": "Bridge authentication is misconfigured"})
                    await ws.close(code=4002)
                    return

                if _BRIDGE_AUTH_REQUIRED or _BRIDGE_AUTH_TOKEN:
                    token = msg.get("token", "")
                    if token != _BRIDGE_AUTH_TOKEN:
                        await ws.send_json({"type": "error", "message": "Invalid auth token"})
                        await ws.close(code=4001)
                        return

                _bridge_clients[client_id] = ws
                await ws.send_json({"type": "ack", "role": role, "client_id": client_id})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "relay":
                target = msg.get("target")
                payload = msg.get("payload", {})
                if target and target in _bridge_clients:
                    await _bridge_clients[target].send_json({
                        "type": "relay",
                        "from": client_id,
                        "payload": payload,
                    })
                else:
                    for cid, cws in _bridge_clients.items():
                        if cid != client_id:
                            await cws.send_json({
                                "type": "relay",
                                "from": client_id,
                                "payload": payload,
                            })

            elif msg_type == "result":
                target = msg.get("target")
                if target and target in _bridge_clients:
                    await _bridge_clients[target].send_json({
                        "type": "result",
                        "from": client_id,
                        "payload": msg.get("payload", {}),
                    })

    except WebSocketDisconnect:
        pass
    finally:
        _bridge_clients.pop(client_id, None)
