"""PCOS Cloud Escalation Layer — policy-gated cloud LLM fallback."""
import os
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("pcos.cloud")


ESCALATION_LOG: list[dict] = []  # In-memory log; replace with DB in T10


class CloudEscalation:
    """Policy-gated cloud LLM fallback. Logs every escalation."""

    def __init__(self, provider: str = "gemini"):
        self.provider = provider
        self.api_key = os.getenv("CLOUD_LLM_API_KEY", "")

    def should_escalate(self, confidence: float, task_type: str, is_long: bool) -> tuple[bool, str]:
        """Determine if escalation is warranted. Returns (should_escalate, reason)."""
        if confidence < 0.7:
            return True, f"Local confidence {confidence:.2f} below threshold"
        if is_long and task_type == "reasoning":
            return True, "Long reasoning task exceeds local model capability"
        return False, ""

    def call(self, prompt: str, context_prefix: str = "", reason: str = "") -> Optional[str]:
        """Call cloud LLM. Strips private context before sending."""
        self._log_escalation(reason)
        full_prompt = f"{context_prefix}\n\n{prompt}".strip() if context_prefix else prompt
        # TODO: wire to Gemini / OpenAI SDK in T9
        log.warning(f"Cloud escalation triggered: {reason}")
        return None

    def _log_escalation(self, reason: str):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": self.provider,
            "reason": reason,
        }
        ESCALATION_LOG.append(entry)
        log.info(f"Escalation logged: {entry}")

    @staticmethod
    def get_log() -> list[dict]:
        return ESCALATION_LOG
