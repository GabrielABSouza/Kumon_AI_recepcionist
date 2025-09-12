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
        "app.core.state_manager.redis_client",
    ]

    for path in redis_paths:
        try:
            module_path, attr = path.rsplit(".", 1)
            mod = __import__(module_path, fromlist=[attr])
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, fake, raising=False)
        except Exception:
            pass

    # Patch specific state manager functions
    try:
        import app.core.state_manager as sm

        def mock_get_conversation_state(phone):
            del phone  # Unused parameter
            return {}

        def mock_save_conversation_state(phone, data):
            del phone, data  # Unused parameters
            return True

        def mock_get_conversation_history(phone, limit=10):
            del phone, limit  # Unused parameters
            return []

        monkeypatch.setattr(
            sm, "get_conversation_state", mock_get_conversation_state, raising=False
        )
        monkeypatch.setattr(
            sm, "save_conversation_state", mock_save_conversation_state, raising=False
        )
        monkeypatch.setattr(
            sm, "get_conversation_history", mock_get_conversation_history, raising=False
        )
    except Exception:
        pass

    return fake


@pytest.fixture
def mock_gemini(monkeypatch):
    """Mock Gemini classifier for testing."""

    class MockClassifier:
        def classify(self, text: str, context=None):
            del context  # Unused parameter
            # Simple mock classification based on keywords
            text_lower = text.lower()

            # Extract entities based on text content
            entities = {}
            if "gabriel" in text_lower:
                entities["parent_name"] = "Gabriel"
            if "matemática" in text_lower:
                entities["program_interests"] = ["Matemática"]

            if "oi" in text_lower or "olá" in text_lower:
                # For complex greetings with information request
                if "informações" in text_lower or "método" in text_lower:
                    return {
                        "primary_intent": "information",
                        "secondary_intent": None,
                        "entities": entities,
                        "confidence": 0.95,
                    }
                else:
                    return {
                        "primary_intent": "greeting",
                        "secondary_intent": None,
                        "entities": entities,
                        "confidence": 0.95,
                    }
            elif "matricular" in text_lower:
                return {
                    "primary_intent": "qualification",
                    "secondary_intent": None,
                    "entities": entities,
                    "confidence": 0.90,
                }
            elif "método" in text_lower or "informações" in text_lower:
                return {
                    "primary_intent": "information",
                    "secondary_intent": None,
                    "entities": entities,
                    "confidence": 0.85,
                }
            elif "agendar" in text_lower:
                return {
                    "primary_intent": "scheduling",
                    "secondary_intent": None,
                    "entities": entities,
                    "confidence": 0.88,
                }
            else:
                return {
                    "primary_intent": "fallback",
                    "secondary_intent": None,
                    "entities": {},
                    "confidence": 0.50,
                }

    mock_instance = MockClassifier()

    # Patch all possible import locations
    import_locations = [
        "app.core.gemini_classifier",
        "app.core.routing.master_router",
        "app.core.langgraph_flow",
        "app.core.unified_service_resolver",
        "app.core.service_registry",
        "app.core.service_factory",
        "app.core.router.smart_router_adapter",
    ]

    for location in import_locations:
        try:
            mod = __import__(location, fromlist=["classifier"])
            if hasattr(mod, "classifier"):
                monkeypatch.setattr(mod, "classifier", mock_instance, raising=False)
                print(f"Patched classifier in {location}")
        except Exception as e:
            print(f"Failed to patch classifier in {location}: {e}")

    return MockClassifier()


@pytest.fixture
def mock_delivery(monkeypatch):
    """Mock delivery service to avoid actual API calls."""
    from tests.utils.fakes import CallRecorder

    # Create recorder that returns proper format
    recorder = CallRecorder(return_value={"sent": "true", "status": "success"})

    try:
        import app.core.delivery as delivery

        monkeypatch.setattr(delivery, "send_text", recorder, raising=False)
    except Exception:
        pass

    return recorder


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI for testing."""

    class MockOpenAIClient:
        async def chat(
            self,
            model=None,
            system_prompt=None,
            user_prompt=None,
            temperature=None,
            max_tokens=None,
        ):
            """Mock chat method that returns a response based on user input."""
            del model, system_prompt, temperature, max_tokens  # Unused params
            # Return a smart response based on the user prompt
            if "informações" in user_prompt.lower() or "método" in user_prompt.lower():
                return (
                    "Olá Gabriel! O Kumon de Matemática é um método "
                    "individualizado que fortalece o raciocínio. "
                    "Para que eu possa te ajudar melhor, o Kumon é para "
                    "você mesmo ou para outra pessoa?"
                )
            return "Olá! Sou Cecília do Kumon. Como posso ajudar?"

    try:
        import app.core.llm.openai_adapter as openai_adapter

        monkeypatch.setattr(
            openai_adapter, "OpenAIClient", MockOpenAIClient, raising=False
        )
    except Exception:
        pass

    return MockOpenAIClient


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
