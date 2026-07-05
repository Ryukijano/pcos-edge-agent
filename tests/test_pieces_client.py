"""Tests for PiecesOS MCP connector — PiecesConnector.

Tests cover:
- Query with mocked SSE/HTTP responses
- Graceful offline fallback (connection refused → empty list)
- PII stripping on LTM results
- MemoryItem dataclass
- Helper methods (get_recent_snippets, get_recent_projects, get_todos)
"""
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from memory.pieces.connector import (
    PiecesConnector,
    MemoryItem,
    PIECES_MCP_BASE,
    PIECES_QUERY_ENDPOINT,
    PIECES_HEALTH_ENDPOINT,
)


# ── MemoryItem tests ───────────────────────────────────────────


class TestMemoryItem:
    def test_init_defaults(self):
        item = MemoryItem()
        assert item.content == ""
        assert item.title == ""
        assert item.score == 0.0
        assert item.raw == {}

    def test_init_with_values(self):
        item = MemoryItem(
            content="some code",
            title="snippet.py",
            source="vscode",
            timestamp="2026-01-01",
            score=0.95,
        )
        assert item.content == "some code"
        assert item.title == "snippet.py"
        assert item.score == 0.95

    def test_to_dict(self):
        item = MemoryItem(content="hello", title="test", score=0.8)
        d = item.to_dict()
        assert d["content"] == "hello"
        assert d["title"] == "test"
        assert d["score"] == 0.8

    def test_repr(self):
        item = MemoryItem(title="my_snippet", score=0.5)
        assert "my_snippet" in repr(item)
        assert "0.50" in repr(item)


# ── PiecesConnector availability ───────────────────────────────


class TestPiecesConnectorAvailability:
    def test_is_available_false_when_not_running(self):
        connector = PiecesConnector(base_url="http://localhost:99999")
        assert connector.is_available() is False

    def test_is_available_caches_result(self):
        connector = PiecesConnector(base_url="http://localhost:99999")
        connector._available = True
        connector._last_check = float("inf")  # never expire
        assert connector.is_available() is True

    @patch("memory.pieces.connector.httpx.get")
    def test_is_available_true_when_responding(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        connector = PiecesConnector(base_url="http://localhost:39300")
        assert connector.is_available() is True


# ── PiecesConnector query with mocked responses ────────────────


class TestPiecesConnectorQuery:
    @patch("memory.pieces.connector.httpx.get")
    def test_query_returns_empty_when_unavailable(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500)
        connector = PiecesConnector(base_url="http://localhost:99999")
        results = connector.query("test query")
        assert results == []

    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_query_returns_parsed_results(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {
                    "content": [
                        {"text": json.dumps([
                            {
                                "content": "def hello(): pass",
                                "title": "hello.py",
                                "source": "vscode",
                                "timestamp": "2026-01-01",
                                "score": 0.9,
                            }
                        ])}
                    ]
                }
            }),
        )
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("hello function")
        assert len(results) == 1
        assert results[0]["content"] == "def hello(): pass"
        assert results[0]["title"] == "hello.py"

    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_query_handles_exception_gracefully(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.side_effect = Exception("Connection refused")
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("test")
        assert results == []

    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_query_strips_pii_from_results(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {
                    "content": [
                        {"text": json.dumps([
                            {
                                "content": "Contact john@example.com for details",
                                "title": "Email snippet",
                                "score": 0.8,
                            }
                        ])}
                    ]
                }
            }),
        )
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("email")
        assert len(results) == 1
        assert "[EMAIL]" in results[0]["content"]
        assert "john@example.com" not in results[0]["content"]


# ── PiecesConnector async query ────────────────────────────────


class TestPiecesConnectorAsync:
    @pytest.mark.asyncio
    @patch.object(PiecesConnector, "is_available", return_value=False)
    async def test_query_async_returns_empty_when_unavailable(self, _):
        connector = PiecesConnector(base_url="http://localhost:99999")
        results = await connector.query_async("test")
        assert results == []

    @pytest.mark.asyncio
    @patch.object(PiecesConnector, "is_available", return_value=True)
    async def test_query_async_returns_parsed_results(self, _):
        connector = PiecesConnector(base_url="http://localhost:39300")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "result": {
                "content": [
                    {"text": json.dumps([
                        {
                            "content": "async snippet",
                            "title": "async.py",
                            "score": 0.85,
                        }
                    ])}
                ]
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        connector._async_client = mock_client

        results = await connector.query_async("async test")
        assert len(results) == 1
        assert results[0]["content"] == "async snippet"

    @pytest.mark.asyncio
    @patch.object(PiecesConnector, "is_available", return_value=True)
    async def test_query_async_strips_pii(self, _):
        connector = PiecesConnector(base_url="http://localhost:39300")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "result": {
                "content": [
                    {"text": json.dumps([
                        {
                            "content": "Key: sk-1234567890abcdefghijklmnop",
                            "title": "config.py",
                            "score": 0.7,
                        }
                    ])}
                ]
            }
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        connector._async_client = mock_client

        results = await connector.query_async("api key")
        assert len(results) == 1
        assert "[API_KEY]" in results[0]["content"]
        assert "sk-1234567890abcdefghijklmnop" not in results[0]["content"]


# ── PII stripping integration ──────────────────────────────────


class TestPIIStrippingOnLTM:
    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_email_stripped(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {"content": [{"text": json.dumps([
                    {"content": "Send to alice@company.com", "title": "Email"}
                ])}]}
            }),
        )
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("email")
        assert "alice@company.com" not in results[0]["content"]
        assert "[EMAIL]" in results[0]["content"]

    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_phone_stripped(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {"content": [{"text": json.dumps([
                    {"content": "Call +1-555-123-4567", "title": "Phone"}
                ])}]}
            }),
        )
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("phone")
        assert "555-123-4567" not in results[0]["content"]

    @patch("memory.pieces.connector.httpx.get")
    @patch("memory.pieces.connector.httpx.post")
    def test_multiple_pii_types_stripped(self, mock_post, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {"content": [{"text": json.dumps([
                    {
                        "content": "Email: bob@x.com, Phone: 555-000-1111, IP: 10.0.0.1",
                        "title": "Contact info for bob@x.com",
                    }
                ])}]}
            }),
        )
        connector = PiecesConnector(base_url="http://localhost:39300")
        results = connector.query("contact")
        assert "bob@x.com" not in results[0]["content"]
        assert "555-000-1111" not in results[0]["content"]
        assert "10.0.0.1" not in results[0]["content"]
        assert "[EMAIL]" in results[0]["content"]
        assert "[PHONE]" in results[0]["content"]
        assert "[IP]" in results[0]["content"]
        assert "[EMAIL]" in results[0]["title"]


# ── Helper methods ─────────────────────────────────────────────


class TestHelperMethods:
    @patch.object(PiecesConnector, "query")
    def test_get_recent_snippets(self, mock_query):
        mock_query.return_value = [
            {"content": "snippet 1", "title": "a.py"},
            {"content": "snippet 2", "title": "b.py"},
        ]
        connector = PiecesConnector()
        snippets = connector.get_recent_snippets(limit=2)
        assert snippets == ["snippet 1", "snippet 2"]

    @patch.object(PiecesConnector, "query")
    def test_get_recent_projects(self, mock_query):
        mock_query.return_value = [
            {"content": "", "title": "PCOS"},
            {"content": "", "title": "LiteRT-LM"},
        ]
        connector = PiecesConnector()
        projects = connector.get_recent_projects(limit=2)
        assert projects == ["PCOS", "LiteRT-LM"]

    @patch.object(PiecesConnector, "query")
    def test_get_todos(self, mock_query):
        mock_query.return_value = [
            {"content": "Fix bug #123", "title": ""},
            {"content": "Write tests", "title": ""},
        ]
        connector = PiecesConnector()
        todos = connector.get_todos(limit=2)
        assert todos == ["Fix bug #123", "Write tests"]

    @patch.object(PiecesConnector, "query")
    def test_get_recent_snippets_filters_empty(self, mock_query):
        mock_query.return_value = [
            {"content": "real snippet", "title": "a.py"},
            {"content": "", "title": "empty.py"},
        ]
        connector = PiecesConnector()
        snippets = connector.get_recent_snippets(limit=2)
        assert snippets == ["real snippet"]
