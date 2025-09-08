"""
Pytest configuration and fixtures for ONE_TURN architecture tests.
"""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Get FastAPI application instance."""
    from main import app

    return app


@pytest_asyncio.fixture
async def async_client(app):
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def patch_redis(monkeypatch):
    """
    Replace Redis with FakeRedis for testing.
    Patches various points where Redis might be accessed.
    """
    from tests.utils.fakes import FakeRedis

    fake = FakeRedis()

    # Patch turn controller if it uses Redis
    try:
        import app.core.dedup as dedup_module

        # Replace the global turn_controller with a fresh instance
        # that will use our fake Redis if needed
        monkeypatch.setattr(
            dedup_module,
            "turn_controller",
            dedup_module.TurnController(ttl_seconds=60),
            raising=False,
        )
    except Exception:
        pass

    # If there's a Redis client somewhere, patch it
    redis_paths = [
        "app.core.dedup.redis_client",
        "app.core.cache_manager.redis_client",
        "app.services.message_preprocessor.redis_client",
    ]

    for path in redis_paths:
        try:
            module_path, attr = path.rsplit(".", 1)
            mod = __import__(module_path, fromlist=[attr])
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, fake, raising=False)
        except Exception:
            pass

    return fake


@pytest.fixture
def mock_gemini(monkeypatch):
    """Mock Gemini classifier for testing."""

    class MockClassifier:
        def classify(self, text: str):
            # Simple mock classification based on keywords
            if "oi" in text.lower() or "olá" in text.lower():
                return ("greeting", 0.95)
            elif "matricular" in text.lower():
                return ("qualification", 0.90)
            elif "método" in text.lower():
                return ("information", 0.85)
            elif "agendar" in text.lower():
                return ("scheduling", 0.88)
            else:
                return ("fallback", 0.50)

    try:
        import app.core.gemini_classifier as gc

        monkeypatch.setattr(gc, "classifier", MockClassifier(), raising=False)
    except Exception:
        pass

    return MockClassifier()


@pytest.fixture
def mock_delivery(monkeypatch):
    """Mock delivery service to avoid actual API calls."""
    from tests.utils.fakes import CallRecorder

    recorder = CallRecorder()

    try:
        import app.core.delivery as delivery

        monkeypatch.setattr(delivery, "send_text", recorder, raising=False)
    except Exception:
        pass

    return recorder


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI for testing."""

    class MockOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(**kwargs):  # noqa: U100
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "Olá! Sou Cecília do Kumon. Como posso ajudar?"
                            }
                        }
                    ]
                }

    try:
        pass

        monkeypatch.setattr(
            "openai.ChatCompletion", MockOpenAI.ChatCompletion, raising=False
        )
    except Exception:
        pass

    return MockOpenAI


# Gemini Orchestrator fixtures
@pytest.fixture
def gemini_stub():
    """Basic Gemini API stub."""
    from tests.helpers.gemini_stubs import GeminiStub

    return GeminiStub()


@pytest.fixture
def context_aware_gemini_stub():
    """Context-aware Gemini stub."""
    from tests.helpers.gemini_stubs import ContextAwareGeminiStub

    return ContextAwareGeminiStub()


@pytest.fixture
def threshold_aware_gemini_stub():
    """Threshold-aware Gemini stub."""
    from tests.helpers.gemini_stubs import ThresholdAwareGeminiStub

    return ThresholdAwareGeminiStub()


@pytest.fixture
def performance_gemini_stub():
    """Performance testing Gemini stub."""
    from tests.helpers.gemini_stubs import PerformanceTestGeminiStub

    return PerformanceTestGeminiStub()


@pytest.fixture
def base_msg():
    """Basic preprocessed message for testing."""
    from tests.helpers.factories import MessageFactory

    return MessageFactory.create_simple_message()
