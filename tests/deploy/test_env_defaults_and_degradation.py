"""
Test graceful degradation when services are unavailable.
Ensures app doesn't crash when DB/Redis are missing.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.timeout(15)
def test_startup_without_db_and_redis(monkeypatch):
    """App should start even without DB/Redis (degraded mode)."""
    # Remove DB/Redis URLs to simulate unavailable services
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("REDIS_HOST", raising=False)

    # Set minimal required variables
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EVOLUTION_API_URL", "https://example.com")
    monkeypatch.setenv("EVOLUTION_API_INSTANCE", "test-instance")
    monkeypatch.setenv("EVOLUTION_API_TOKEN", "test-token")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # App should be running even without DB/Redis
        r = client.get("/health", follow_redirects=False)
        # Accept 200, 204, or 404 (endpoint might not exist but app is running)
        msg = f"Unexpected status {r.status_code}: {r.text}"
        assert r.status_code in (200, 204, 404), msg


@pytest.mark.timeout(15)
def test_missing_evolution_vars_should_fail_fast(monkeypatch):
    """Missing critical Evolution API vars should fail with clear error."""
    # Remove all Evolution API variables
    critical_vars = [
        "EVOLUTION_API_URL",
        "EVOLUTION_API_INSTANCE",
        "EVOLUTION_API_TOKEN",
    ]

    for var in critical_vars:
        monkeypatch.delenv(var, raising=False)

    # The app should fail to start or validate config
    with pytest.raises(Exception) as exc_info:
        from fastapi.testclient import TestClient

        from app.main import app

        # Try to start the app
        with TestClient(app):
            pass

    # The error should mention the missing config
    error_msg = str(exc_info.value).lower()
    assert any(
        keyword in error_msg
        for keyword in ["evolution", "config", "environment", "required", "missing"]
    ), f"Error message not helpful: {exc_info.value}"


@pytest.mark.timeout(10)
def test_optional_services_can_be_missing(monkeypatch):
    """Optional services (OpenAI, Google) can be missing."""
    # Set required vars
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EVOLUTION_API_URL", "https://example.com")
    monkeypatch.setenv("EVOLUTION_API_INSTANCE", "test")
    monkeypatch.setenv("EVOLUTION_API_TOKEN", "test-token")

    # Remove optional service credentials
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # Should still work without AI services
        r = client.get("/")
        # Not failing is success here
        assert r.status_code != 500, "App crashed without optional services"


@pytest.mark.timeout(10)
def test_health_endpoint_in_degraded_mode(monkeypatch):
    """Health endpoint should work even in degraded mode."""
    # Minimal config
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EVOLUTION_API_URL", "https://example.com")
    monkeypatch.setenv("EVOLUTION_API_INSTANCE", "test")
    monkeypatch.setenv("EVOLUTION_API_TOKEN", "test-token")

    # Remove everything else
    for var in ["DATABASE_URL", "REDIS_URL", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
        monkeypatch.delenv(var, raising=False)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        # Try common health endpoint patterns
        for endpoint in ["/health", "/healthz", "/api/health"]:
            r = client.get(endpoint)
            if r.status_code != 404:
                # Found a health endpoint
                status_msg = (
                    f"Health endpoint returned unexpected status: {r.status_code}"
                )
                assert r.status_code in (200, 204, 503), status_msg
                break
