"""PCOS Privacy Policy — PII stripping and context sanitisation.

All text destined for cloud escalation passes through here.
Local surfaces (Chrome, Android) do not need stripping — data stays on device.
"""
from __future__ import annotations

import re

# ── PII patterns ───────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_API_KEY_RE = re.compile(r"(?:sk-|pk-|Bearer\s)[a-zA-Z0-9]{20,}")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_ADDRESS_RE = re.compile(r"\b\d{1,5}\s+[A-Z][a-zA-Z]+\s+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Rd|Road|Way|Court|Ct|Place|Pl)\b")

# Names are harder to detect reliably; we use a simple heuristic for
# "[Name: ...]" patterns that the context schema itself produces.
_BRACKETED_NAME_RE = re.compile(r"\[(?:Name|User|Author|From|To):\s*[^\]]+\]", re.I)

_REPLACEMENTS = [
    (_EMAIL_RE, "[EMAIL]"),
    (_PHONE_RE, "[PHONE]"),
    (_IP_RE, "[IP]"),
    (_API_KEY_RE, "[API_KEY]"),
    (_CREDIT_CARD_RE, "[CARD]"),
    (_SSN_RE, "[SSN]"),
    (_ADDRESS_RE, "[ADDRESS]"),
    (_BRACKETED_NAME_RE, "[NAME]"),
]


def strip_pii(text: str) -> str:
    """Replace PII patterns with redaction tokens.

    Args:
        text: The text to sanitise.

    Returns:
        Text with emails, phone numbers, IPs, API keys, credit cards, and
        bracketed name fields replaced by redaction tokens.
    """
    result = text
    for pattern, replacement in _REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def is_safe_for_cloud(text: str) -> bool:
    """Check if text has already been stripped of PII.

    Returns True if no raw PII patterns are found.
    """
    for pattern, _ in _REPLACEMENTS:
        if pattern.search(text):
            return False
    return True


def strip_context_for_cloud(context_payload: dict) -> dict:
    """Strip PII from all string values in a context payload dict.

    Args:
        context_payload: The payload dict from the router.

    Returns:
        A new dict with all string values PII-stripped.
    """
    stripped: dict = {}
    for key, value in context_payload.items():
        if isinstance(value, str):
            stripped[key] = strip_pii(value)
        elif isinstance(value, list):
            stripped[key] = [strip_pii(v) if isinstance(v, str) else v for v in value]
        else:
            stripped[key] = value
    stripped["pii_stripped"] = True
    return stripped
