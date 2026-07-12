"""M25 release security regression tests.

These tests guard the release gates identified by the M25 security audit:
- version consistency across package/API/extension metadata
- restrictive CORS defaults
- explicit bridge authentication mode
- cloud PII sanitisation and provider-key handling
- minimal Android/Chrome permission declarations
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from broker.config import Settings
from broker.main import app
from broker.policies.privacy import is_safe_for_cloud, strip_pii


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent():
    pyproject = (ROOT / "pyproject.toml").read_text()
    manifest = json.loads((ROOT / "apps/chrome-extension/manifest.json").read_text())
    assert 'version = "1.0.0"' in pyproject
    assert manifest["version"] == "1.0.0"


def test_api_reports_release_version():
    with TestClient(app) as client:
        health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["version"] == "1.0.0"


def test_cors_default_is_not_wildcard():
    settings = Settings()
    assert "*" not in settings.cors_origins


def test_bridge_auth_can_be_required_without_a_token():
    settings = Settings(bridge_auth_required=True, bridge_auth_token="")
    assert settings.bridge_auth_required is True
    assert settings.bridge_auth_token == ""


def test_cloud_payload_is_safe_after_redaction():
    raw = "Email jane@example.com, phone +1 415-555-0134, key sk-abcdefghijklmnopqrstuv"
    stripped = strip_pii(raw)
    assert is_safe_for_cloud(stripped)
    assert "jane@example.com" not in stripped
    assert "415-555-0134" not in stripped
    assert "sk-abcdefghijklmnopqrstuv" not in stripped


def test_env_example_has_no_secret_values():
    env_example = (ROOT / ".env.example").read_text()
    assert "sk-" not in env_example
    assert "AIza" not in env_example
    assert "BEGIN PRIVATE KEY" not in env_example


def test_android_manifest_declares_optional_native_accelerators():
    manifest = (ROOT / "apps/android/app/src/main/AndroidManifest.xml").read_text()
    assert 'android:name="libQnnHtp.so" android:required="false"' in manifest
    assert 'android:name="libOpenCL.so" android:required="false"' in manifest


def test_chrome_manifest_has_no_broad_external_host():
    manifest = json.loads((ROOT / "apps/chrome-extension/manifest.json").read_text())
    assert "<all_urls>" not in manifest["host_permissions"]
    assert "http://localhost:8000/*" in manifest["host_permissions"]


def test_docker_files_have_no_wildcard_cors():
    dockerfile = (ROOT / "Dockerfile").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert 'CORS_ORIGINS=["*"]' not in dockerfile
    assert 'CORS_ORIGINS=["*"]' not in compose
