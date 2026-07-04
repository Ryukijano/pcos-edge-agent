"""PCOS Escalation Policy — gates and logs every cloud LLM escalation.

Cloud is the last resort, never the default. Every escalation must:
1. Pass the should_escalate() check (confidence, length, explicit user request)
2. Have PII stripped from the payload (via privacy.strip_context_for_cloud)
3. Be logged with timestamp, reason, and provider
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger("pcos.escalation")


class EscalationEvent(BaseModel):
    timestamp: str
    reason: str
    provider: str = ""
    task_text_preview: str = ""
    confidence: float = 0.0
    user_explicit: bool = False


# In-memory log; backed by SQLite in broker/main.py metrics layer
_ESCALATION_LOG: list[EscalationEvent] = []


def should_escalate(
    confidence: float,
    task_type: str,
    is_long: bool,
    user_explicit: bool = False,
    threshold: float = 0.7,
) -> tuple[bool, str]:
    """Determine if cloud escalation is warranted.

    Args:
        confidence: Local model confidence score (0–1).
        task_type: transform | action | reasoning | retrieval.
        is_long: Whether the task exceeds local context limits.
        user_explicit: Whether the user explicitly asked for cloud.
        threshold: Confidence threshold below which escalation triggers.

    Returns:
        (should_escalate, reason) tuple.
    """
    if user_explicit:
        return True, "User explicitly requested cloud escalation"
    if confidence < threshold:
        return True, f"Local confidence {confidence:.2f} below threshold {threshold}"
    if is_long and task_type == "reasoning":
        return True, "Long reasoning task exceeds local model capability"
    return False, ""


def log_escalation(
    reason: str,
    provider: str = "",
    task_text: str = "",
    confidence: float = 0.0,
    user_explicit: bool = False,
) -> EscalationEvent:
    """Log an escalation event and return it."""
    event = EscalationEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        reason=reason,
        provider=provider,
        task_text_preview=task_text[:100],
        confidence=confidence,
        user_explicit=user_explicit,
    )
    _ESCALATION_LOG.append(event)
    log.warning(f"Cloud escalation: {reason} | provider={provider} | explicit={user_explicit}")
    return event


def get_escalation_log() -> list[EscalationEvent]:
    """Return all logged escalation events."""
    return list(_ESCALATION_LOG)


def clear_escalation_log() -> None:
    """Clear the in-memory log (use after persisting to SQLite)."""
    _ESCALATION_LOG.clear()
