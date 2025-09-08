"""
Smoke test for FastAPI startup.
Catches errors like missing modules and initialization failures.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Add root to path
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def minimal_env(monkeypatch):
    """Set minimal environment variables for testing."""
    # Essential Evolution API variables
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EVOLUTION_API_URL", "https://example.com")
    monkeypatch.setenv("EVOLUTION_API_INSTANCE", "test-instance")
    monkeypatch.setenv("EVOLUTION_API_TOKEN", "test-token-123")

    # Optional: can be missing (app should degrade gracefully)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    return monkeypatch


@pytest.mark.timeout(15)
def test_fastapi_startup_smoke(minimal_env):  # noqa: U100
    """Test that FastAPI app can start with minimal config."""
    try:
        from app.main import app
    except Exception as e:
        pytest.fail(f"Failed to import app.main: {e}")

    # TestClient triggers lifespan events (startup/shutdown)
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # Try to hit a basic endpoint
        # Adjust path based on your actual endpoints
        for endpoint in ["/health", "/healthz", "/", "/docs"]:
            r = client.get(endpoint)
            if r.status_code in (200, 204, 404):
                # 200/204 = success, 404 = endpoint doesn't exist but app is running
                break
        else:
            pytest.fail("No valid endpoint responded during smoke test")


@pytest.mark.timeout(10)
def test_app_has_required_routers(minimal_env):  # noqa: U100
    """Test that essential routers are registered."""
    from app.main import app

    # Check that app has routes
    assert len(app.routes) > 0, "App has no routes registered"

    # Check for specific paths (adjust based on your app)
    paths = [route.path for route in app.routes]

    # At minimum, should have some API routes
    api_routes = [p for p in paths if p.startswith("/api") or p.startswith("/webhook")]
    assert len(api_routes) > 0, f"No API routes found. Available: {paths}"


@pytest.mark.timeout(10)
def test_startup_events_dont_crash(minimal_env):  # noqa: U100
    """Test that startup events complete without crashing."""
    from fastapi.testclient import TestClient

    from app.main import app

    startup_completed = False

    @app.on_event("startup")
    async def test_startup_marker():
        nonlocal startup_completed
        startup_completed = True

    with TestClient(app):
        assert startup_completed, "Startup events did not complete"
