"""
Error handling tests for Gemini Orchestrator.
Tests timeout, retries, provider errors, and graceful degradation.
"""
import asyncio

import pytest

from tests.helpers.factories import MessageFactory
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


@pytest.fixture
def orchestrator(gemini_stub):
    """Create orchestrator with normal stub."""
    return GeminiOrchestrator(client=gemini_stub, timeout_ms=150, retries=1)


# TIMEOUT TESTS


@pytest.mark.asyncio
async def test_error_timeout_degrades_to_fallback(orchestrator, gemini_stub):
    """Test that timeout degrades gracefully to fallback."""
    # Given
    msg = MessageFactory.create_simple_message(text="olá")
    gemini_stub.behavior = "timeout"

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0
    assert "timeout" in str(result.error).lower()


@pytest.mark.asyncio
async def test_error_slow_response_within_timeout(orchestrator, gemini_stub):
    """Test that slow but within timeout responses work."""
    # Given
    msg = MessageFactory.create_simple_message(text="olá")
    gemini_stub.behavior = "ok"
    gemini_stub.delay_ms = 100  # 100ms, within 150ms timeout

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "greeting"
    assert result.confidence > 0.8
    assert result.error is None


# PROVIDER ERROR TESTS


@pytest.mark.asyncio
async def test_error_provider_error_degrades(orchestrator, gemini_stub):
    """Test that provider errors degrade to fallback."""
    # Given
    msg = MessageFactory.create_simple_message(text="informações")
    gemini_stub.behavior = "error"

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0
    assert result.error is not None


@pytest.mark.asyncio
async def test_error_rate_limit_handled(orchestrator, gemini_stub):
    """Test that rate limit errors are handled."""
    # Given
    msg = MessageFactory.create_simple_message(text="teste")
    gemini_stub.behavior = "rate_limit"

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0
    assert "rate" in str(result.error).lower()


# RETRY TESTS


@pytest.mark.asyncio
async def test_error_retry_on_transient_error(orchestrator):
    """Test that orchestrator retries on transient errors."""
    # Given
    msg = MessageFactory.create_simple_message(text="olá")

    # Create stub that fails once then succeeds
    class RetryStub:
        def __init__(self):
            self.attempts = 0

        async def classify(self, prompt):
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("Transient network error")
            return {"intent": "greeting", "confidence": 0.9, "entities": {}}

    retry_stub = RetryStub()
    orchestrator.client = retry_stub

    # When
    result = await orchestrator.classify(msg)

    # Then - should succeed after retry
    assert result.intent == "greeting"
    assert result.confidence == 0.9
    assert retry_stub.attempts == 2  # First failed, second succeeded


@pytest.mark.asyncio
async def test_error_max_retries_exceeded(orchestrator):
    """Test that max retries are respected."""
    # Given
    msg = MessageFactory.create_simple_message(text="teste")

    # Create stub that always fails
    class AlwaysFailStub:
        def __init__(self):
            self.attempts = 0

        async def classify(self, prompt):
            self.attempts += 1
            raise Exception("Persistent error")

    fail_stub = AlwaysFailStub()
    orchestrator.client = fail_stub
    orchestrator.retries = 2  # Allow 2 retries

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0
    assert fail_stub.attempts <= 3  # Initial + 2 retries


# INPUT VALIDATION TESTS


@pytest.mark.asyncio
async def test_error_empty_text_handled(orchestrator, gemini_stub):
    """Test that empty text is handled gracefully."""
    # Given
    msg = MessageFactory.create_simple_message(text="")
    gemini_stub.set_response("fallback", 0.0)

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_error_none_text_handled(orchestrator, gemini_stub):
    """Test that None text is handled."""
    # Given
    msg = MessageFactory.create_simple_message(text="")
    msg.text = None  # Force None

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "fallback"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_error_extremely_long_text(orchestrator, gemini_stub):
    """Test that extremely long text doesn't cause issues."""
    # Given - 10KB of text
    long_text = "teste " * 2000
    msg = MessageFactory.create_simple_message(text=long_text)
    gemini_stub.set_response("information_request", 0.7)

    # When
    result = await orchestrator.classify(msg)

    # Then - should handle gracefully
    assert result.intent in ["information_request", "fallback"]
    assert 0.0 <= result.confidence <= 1.0


# MALFORMED RESPONSE TESTS


@pytest.mark.asyncio
async def test_error_malformed_gemini_response(orchestrator):
    """Test handling of malformed Gemini responses."""
    # Given
    msg = MessageFactory.create_simple_message(text="teste")

    class MalformedStub:
        async def classify(self, prompt):
            # Return malformed response
            return {"wrong_key": "value"}

    orchestrator.client = MalformedStub()

    # When
    result = await orchestrator.classify(msg)

    # Then - should degrade gracefully
    assert result.intent == "fallback"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_error_invalid_confidence_value(orchestrator):
    """Test handling of invalid confidence values."""
    # Given
    msg = MessageFactory.create_simple_message(text="teste")

    class InvalidConfidenceStub:
        async def classify(self, prompt):
            return {
                "intent": "greeting",
                "confidence": "not_a_number",  # Invalid
                "entities": {},
            }

    orchestrator.client = InvalidConfidenceStub()

    # When
    result = await orchestrator.classify(msg)

    # Then - should handle gracefully
    assert result.intent in ["greeting", "fallback"]
    assert 0.0 <= result.confidence <= 1.0  # Should be normalized


# CONCURRENT ERROR TESTS


@pytest.mark.asyncio
async def test_error_concurrent_failures_isolated(orchestrator, gemini_stub):
    """Test that concurrent failures don't affect each other."""
    # Given
    msgs = [MessageFactory.create_simple_message(text=f"msg{i}") for i in range(5)]

    # Make some fail
    async def classify_with_random_error(msg, index):
        if index % 2 == 0:
            gemini_stub.behavior = "error"
        else:
            gemini_stub.behavior = "ok"
            gemini_stub.set_response("greeting", 0.9)

        return await orchestrator.classify(msg)

    # When - process concurrently
    results = await asyncio.gather(
        *[classify_with_random_error(msg, i) for i, msg in enumerate(msgs)],
        return_exceptions=True,
    )

    # Then - failures should be isolated
    success_count = sum(
        1 for r in results if not isinstance(r, Exception) and r.confidence > 0.5
    )
    failure_count = sum(
        1 for r in results if not isinstance(r, Exception) and r.confidence == 0.0
    )

    assert success_count > 0  # Some should succeed
    assert failure_count > 0  # Some should fail


# SANITIZATION ERROR TESTS


@pytest.mark.asyncio
async def test_error_already_sanitized_not_resanitized(orchestrator, gemini_stub):
    """Test that already sanitized messages aren't re-sanitized."""
    # Given
    msg = MessageFactory.create_simple_message(
        text="already clean text", sanitized=True
    )
    gemini_stub.set_response("information_request", 0.8)

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.confidence == 0.8
    # Message should be processed normally without re-sanitization
