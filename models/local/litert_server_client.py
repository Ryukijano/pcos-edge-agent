"""OpenAI-compatible client for LiteRT-LM local server (lit serve).

This module provides a drop-in replacement for the OpenAI Python client
that routes requests to a local LiteRT-LM server instead of the cloud.

Usage:
    from models.local.litert_server_client import LiteRTServerClient

    client = LiteRTServerClient(base_url="http://localhost:9379")
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gemma4-e2b,gpu,4096",
    )
    print(response["choices"][0]["message"]["content"])

For streaming:
    for chunk in client.chat_completion_stream(
        messages=[{"role": "user", "content": "Tell me a story"}],
        model="gemma4-e2b,gpu",
    ):
        print(chunk, end="", flush=True)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

import httpx


@dataclass
class LiteRTServerClient:
    """Client for the LiteRT-LM OpenAI-compatible server (lit serve).

    The server emulates OpenAI API endpoints:
      - GET  /v1/models          — list available models
      - POST /v1/chat/completions — chat completions (streaming supported)

    Model field format: model_id[,backend][,max_tokens]
    Example: "gemma4-e2b,gpu,4096"
    """

    base_url: str = "http://localhost:9379"
    timeout: float = 60.0
    _client: httpx.Client = field(init=False, default_factory=httpx.Client)

    def __post_init__(self):
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )

    def list_models(self) -> dict:
        """List available models from the local server."""
        resp = self._client.get("/v1/models")
        resp.raise_for_status()
        return resp.json()

    def chat_completion(
        self,
        messages: list[dict],
        model: str = "gemma4-e2b,gpu,8192",
        temperature: float = 1.0,
        max_tokens: int | None = None,
    ) -> dict:
        """Send a chat completion request (non-streaming).

        Args:
            messages: List of {"role": "user|system|assistant", "content": "..."}.
            model: Model field in format "model_id[,backend][,max_tokens]".
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            OpenAI-compatible response dict with choices, usage, etc.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        resp = self._client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    def chat_completion_stream(
        self,
        messages: list[dict],
        model: str = "gemma4-e2b,gpu,8192",
        temperature: float = 1.0,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Stream chat completion tokens via SSE.

        Yields content delta strings as they arrive.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        with self._client.stream("POST", "/v1/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta
                except json.JSONDecodeError:
                    continue

    def is_available(self) -> bool:
        """Check if the local LiteRT-LM server is running."""
        try:
            self.list_models()
            return True
        except Exception:
            return False

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
