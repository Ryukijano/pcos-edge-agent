"""PiecesOS MCP connector — queries Long-Term Memory for relevant context."""
import httpx
from typing import Optional


PIECES_MCP_BASE = "http://localhost:1000"  # Default PiecesOS local port


class PiecesConnector:
    """Query PiecesOS LTM via its local MCP server."""

    def __init__(self, base_url: str = PIECES_MCP_BASE):
        self.base_url = base_url

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def query(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Query PiecesOS LTM for relevant memories given a task description.
        Returns top-k ranked memory items.
        """
        if not self.is_available():
            return []
        try:
            r = httpx.post(
                f"{self.base_url}/mcp/query",
                json={"query": query, "limit": top_k},
                timeout=3.0
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception:
            return []

    def get_recent_snippets(self, limit: int = 5) -> list[str]:
        """Retrieve recent code snippets from PiecesOS."""
        items = self.query("recent code snippets", top_k=limit)
        return [item.get("content", "") for item in items]

    def get_recent_projects(self, limit: int = 3) -> list[str]:
        """Retrieve recently active project names from PiecesOS."""
        items = self.query("recent projects repositories", top_k=limit)
        return [item.get("title", "") for item in items]
