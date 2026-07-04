"""PCOS Cloud Escalation Provider — Gemini and OpenAI integration.

Cloud is the last resort, never the default. This module provides:
1. Gemini via google-genai SDK (preferred — free tier available)
2. OpenAI via openai SDK (fallback)
3. Automatic PII stripping before any cloud call
4. Escalation logging with reason, provider, and latency

Usage:
    from models.cloud.escalation_provider import escalate_to_cloud
    result = await escalate_to_cloud(task_text, system_prompt, provider="gemini")
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from broker.policies.escalation import log_escalation
from broker.policies.privacy import strip_pii, is_safe_for_cloud

log = logging.getLogger("pcos.cloud")


async def escalate_to_cloud(
    task_text: str,
    system_prompt: str = "",
    provider: str = "gemini",
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """Escalate a task to a cloud LLM provider.

    Args:
        task_text: The user's task text (will be PII-stripped).
        system_prompt: Optional system instruction.
        provider: "gemini" or "openai".
        model: Model name override. Defaults to gemini-2.5-flash / gpt-4o-mini.
        max_tokens: Max output tokens.
        temperature: Sampling temperature.

    Returns:
        Cloud LLM response text.

    Raises:
        RuntimeError: If provider is unavailable or API key is missing.
    """
    # Strip PII before sending to cloud
    stripped_text = strip_pii(task_text)
    if not is_safe_for_cloud(stripped_text):
        log.warning("Cloud payload still contains PII after stripping — aborting")
        raise RuntimeError("Cannot escalate: PII stripping incomplete")

    start = time.perf_counter()

    if provider == "gemini":
        result = await _call_gemini(stripped_text, system_prompt, model, max_tokens, temperature)
    elif provider == "openai":
        result = await _call_openai(stripped_text, system_prompt, model, max_tokens, temperature)
    else:
        raise RuntimeError(f"Unknown cloud provider: {provider}")

    elapsed_ms = (time.perf_counter() - start) * 1000

    log_escalation(
        reason="Cloud LLM escalation",
        provider=provider,
        task_text=task_text,
        confidence=0.0,
        user_explicit=False,
    )

    log.info(
        "cloud_escalation_complete",
        extra={
            "provider": provider,
            "model": model or "default",
            "latency_ms": round(elapsed_ms, 2),
            "input_chars": len(stripped_text),
            "output_chars": len(result),
        },
    )

    return result


async def _call_gemini(
    prompt: str,
    system_prompt: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
) -> str:
    """Call Google Gemini via google-genai SDK."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set — cannot escalate to Gemini")

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig
    except ImportError:
        raise RuntimeError("google-genai package not installed. Run: pip install google-genai")

    client = genai.Client(api_key=api_key)
    model_name = model or "gemini-2.5-flash"

    config = GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=temperature,
        system_instruction=system_prompt if system_prompt else None,
    )

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )

    return response.text or ""


async def _call_openai(
    prompt: str,
    system_prompt: str,
    model: Optional[str],
    max_tokens: int,
    temperature: float,
) -> str:
    """Call OpenAI via openai SDK."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — cannot escalate to OpenAI")

    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client = AsyncOpenAI(api_key=api_key)
    model_name = model or "gpt-4o-mini"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content or ""


def get_available_providers() -> list[str]:
    """Return list of cloud providers with valid API keys."""
    providers = []
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        providers.append("gemini")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    return providers
