"""Tests for cloud escalation provider and policy.

Tests:
1. should_escalate() policy logic
2. PII stripping before cloud call
3. get_available_providers() with/without API keys
4. escalate_to_cloud() with no API key raises RuntimeError
5. Escalation logging
6. /execute endpoint returns cloud_result when escalated

Run: python -m pytest tests/test_cloud_escalation.py -v
"""
import os
import pytest
from unittest.mock import AsyncMock, patch

from broker.policies.escalation import (
    should_escalate,
    log_escalation,
    get_escalation_log,
    clear_escalation_log,
)
from broker.policies.privacy import strip_pii, is_safe_for_cloud
from models.cloud.escalation_provider import get_available_providers, escalate_to_cloud


# ── Escalation policy tests ────────────────────────────────────

class TestShouldEscalate:
    def test_user_explicit_escalates(self):
        ok, reason = should_escalate(confidence=0.99, task_type="transform", is_long=False, user_explicit=True)
        assert ok is True
        assert "explicitly" in reason.lower()

    def test_low_confidence_escalates(self):
        ok, reason = should_escalate(confidence=0.3, task_type="transform", is_long=False)
        assert ok is True
        assert "confidence" in reason.lower()

    def test_high_confidence_no_escalation(self):
        ok, reason = should_escalate(confidence=0.95, task_type="transform", is_long=False)
        assert ok is False

    def test_long_reasoning_escalates(self):
        ok, reason = should_escalate(confidence=0.99, task_type="reasoning", is_long=True)
        assert ok is True
        assert "reasoning" in reason.lower()

    def test_long_transform_no_escalation(self):
        ok, _ = should_escalate(confidence=0.95, task_type="transform", is_long=True)
        assert ok is False


# ── PII stripping before cloud ────────────────────────────────

class TestCloudPIIStripping:
    def test_email_stripped_before_cloud(self):
        text = "Contact john@example.com for details"
        stripped = strip_pii(text)
        assert is_safe_for_cloud(stripped) is True
        assert "john@example.com" not in stripped

    def test_ssn_stripped_before_cloud(self):
        text = "My SSN is 123-45-6789"
        stripped = strip_pii(text)
        assert is_safe_for_cloud(stripped) is True
        assert "123-45-6789" not in stripped

    def test_api_key_stripped(self):
        text = "Use key sk-abc123def456ghi789jkl012mno345pqr678"
        stripped = strip_pii(text)
        assert is_safe_for_cloud(stripped) is True


# ── Provider availability ─────────────────────────────────────

class TestProviderAvailability:
    def test_no_providers_without_keys(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert get_available_providers() == []

    def test_gemini_available_with_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        providers = get_available_providers()
        assert "gemini" in providers

    def test_openai_available_with_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        providers = get_available_providers()
        assert "openai" in providers


# ── Escalation without API key ────────────────────────────────

class TestEscalationNoKey:
    @pytest.mark.asyncio
    async def test_gemini_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            await escalate_to_cloud("test task", provider="gemini")

    @pytest.mark.asyncio
    async def test_openai_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            await escalate_to_cloud("test task", provider="openai")

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        with pytest.raises(RuntimeError, match="Unknown cloud provider"):
            await escalate_to_cloud("test task", provider="anthropic")


# ── Escalation logging ────────────────────────────────────────

class TestEscalationLogging:
    def test_log_and_retrieve(self):
        clear_escalation_log()
        event = log_escalation(
            reason="Test escalation",
            provider="gemini",
            task_text="test task text",
            confidence=0.3,
            user_explicit=False,
        )
        assert event.reason == "Test escalation"
        assert event.provider == "gemini"
        assert event.task_text_preview == "test task text"

        log = get_escalation_log()
        assert len(log) == 1
        assert log[0].reason == "Test escalation"

    def test_clear_log(self):
        log_escalation(reason="test")
        clear_escalation_log()
        assert len(get_escalation_log()) == 0


# ── Execute endpoint with cloud_result ────────────────────────

class TestExecuteCloudResult:
    def test_execute_returns_cloud_result_field(self):
        from fastapi.testclient import TestClient
        from broker.main import app

        with TestClient(app) as client:
            resp = client.post("/execute", json={
                "task": {
                    "text": "Write a comprehensive research report",
                    "task_type": "reasoning",
                    "is_short": False,
                    "exceeds_local_limits": True,
                },
                "context": {},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["decision"]["escalate_to_cloud"] is True
            # cloud_result should be present (None if no API keys)
            assert "cloud_result" in data
