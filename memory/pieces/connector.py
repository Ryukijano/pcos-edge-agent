"""PiecesOS MCP connector — queries Long-Term Memory for relevant context.

PiecesOS exposes its LTM-2.7 engine via MCP over SSE on localhost.
This connector queries for relevant memories given a task description
and returns top-k ranked items to the Context Broker.

Default mode: local-only. PiecesOS is optional — broker degrades gracefully.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

log = logging.getLogger("pcos.pieces")


# PiecesOS default local port (39300 is the PiecesOS Suite default)
PIECES_MCP_BASE = "http://localhost:39300"
PIECES_SSE_ENDPOINT = "/model_context_protocol/2024-11-05/sse"
PIECES_QUERY_ENDPOINT = "/model_context_protocol/2025-03-26/mcp"
PIECES_HEALTH_ENDPOINT = "/.well-known/version"


class MemoryItem:
    """A single memory item from PiecesOS LTM."""

    def __init__(
        self,
        content: str = "",
        title: str = "",
        source: str = "",
        timestamp: str = "",
        score: float = 0.0,
        raw: Optional[dict] = None,
    ):
        self.content = content
        self.title = title
        self.source = source
        self.timestamp = timestamp
        self.score = score
        self.raw = raw or {}

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "title": self.title,
            "source": self.source,
            "timestamp": self.timestamp,
            "score": self.score,
        }

    def __repr__(self) -> str:
        return f"MemoryItem(title={self.title!r}, score={self.score:.2f})"


class PiecesConnector:
    """Query PiecesOS LTM via its local MCP server.

    Uses MCP tool calling (ask_pieces_ltm) over SSE/HTTP.
    Falls back gracefully when PiecesOS isn't running.
    """

    def __init__(self, base_url: str = PIECES_MCP_BASE):
        self.base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None
        self._last_check: float = 0.0
        self._async_client: Optional[httpx.AsyncClient] = None

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(3.0),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._async_client

    def is_available(self) -> bool:
        """Check if PiecesOS is running. Caches result for 30s."""
        import time
        now = time.time()
        if self._available is not None and (now - self._last_check) < 30.0:
            return self._available

        try:
            r = httpx.get(f"{self.base_url}{PIECES_HEALTH_ENDPOINT}", timeout=1.5)
            self._available = r.status_code == 200
        except Exception:
            self._available = False
        self._last_check = now
        log.debug(f"PiecesOS available: {self._available}")
        return self._available

    def query(self, query: str, top_k: int = 5) -> list[dict]:
        """Query PiecesOS LTM for relevant memories.

        Returns top-k ranked memory items as dicts.
        Returns empty list if PiecesOS is unavailable.
        """
        if not self.is_available():
            return []

        try:
            r = httpx.post(
                f"{self.base_url}{PIECES_QUERY_ENDPOINT}",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "ask_pieces_ltm",
                        "arguments": {"query": query, "limit": top_k},
                    },
                    "id": 1,
                },
                timeout=3.0,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("result", {}).get("content", [])
            if isinstance(results, list) and results and isinstance(results[0], dict) and "text" in results[0]:
                import json
                parsed = json.loads(results[0]["text"])
                if isinstance(parsed, list):
                    return [self._parse_item(item) for item in parsed[:top_k]]
            return [self._parse_item(item) for item in (results if isinstance(results, list) else [])[:top_k]]
        except Exception as e:
            log.warning(f"PiecesOS query failed: {e}")
            return []

    async def query_async(self, query: str, top_k: int = 5) -> list[dict]:
        """Async query for use in FastAPI endpoints."""
        if not self.is_available():
            return []

        try:
            client = self._get_async_client()
            r = await client.post(
                PIECES_QUERY_ENDPOINT,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "ask_pieces_ltm",
                        "arguments": {"query": query, "limit": top_k},
                    },
                    "id": 1,
                },
                timeout=3.0,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("result", {}).get("content", [])
            if isinstance(results, list) and results and isinstance(results[0], dict) and "text" in results[0]:
                import json
                parsed = json.loads(results[0]["text"])
                if isinstance(parsed, list):
                    return [self._parse_item(item) for item in parsed[:top_k]]
            return [self._parse_item(item) for item in (results if isinstance(results, list) else [])[:top_k]]
        except Exception as e:
            log.warning(f"PiecesOS async query failed: {e}")
            return []

    def query_sse(self, query: str, top_k: int = 5) -> list[dict]:
        """Query via SSE transport — streams results as they arrive.

        Useful for long-running queries where partial results matter.
        """
        if not self.is_available():
            return []

        results: list[dict] = []
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}{PIECES_SSE_ENDPOINT}",
                json={"query": query, "limit": top_k},
                timeout=10.0,
            ) as r:
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])
                        if "result" in data:
                            results.append(self._parse_item(data["result"]))
                        if len(results) >= top_k:
                            break
        except Exception as e:
            log.warning(f"PiecesOS SSE query failed: {e}")
        return results[:top_k]

    def get_recent_snippets(self, limit: int = 5) -> list[str]:
        """Retrieve recent code snippets from PiecesOS."""
        items = self.query("recent code snippets", top_k=limit)
        return [item.get("content", "") for item in items if item.get("content")]

    def get_recent_projects(self, limit: int = 3) -> list[str]:
        """Retrieve recently active project names from PiecesOS."""
        items = self.query("recent projects repositories", top_k=limit)
        return [item.get("title", "") for item in items if item.get("title")]

    def get_todos(self, limit: int = 5) -> list[str]:
        """Retrieve active todo items from PiecesOS."""
        items = self.query("todos tasks pending", top_k=limit)
        return [item.get("content", "") for item in items if item.get("content")]

    def _parse_item(self, raw: dict) -> dict:
        """Parse a raw PiecesOS result into a normalized dict."""
        return {
            "content": raw.get("content", raw.get("text", "")),
            "title": raw.get("title", raw.get("name", "")),
            "source": raw.get("source", raw.get("application", "")),
            "timestamp": raw.get("timestamp", raw.get("created", "")),
            "score": raw.get("score", raw.get("relevance", 0.0)),
        }
