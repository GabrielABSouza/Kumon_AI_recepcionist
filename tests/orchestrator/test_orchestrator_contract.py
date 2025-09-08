"""
Contract tests for Gemini Orchestrator.
Tests the basic interface and contract requirements.
"""
import pytest

from tests.helpers.factories import MessageFactory, ResultFactory


# Mock orchestrator for testing (will be replaced with real implementation)
class GeminiOrchestrator:
    """Orchestrator that classifies messages using Gemini."""

    def __init__(self, client=None, timeout_ms=150, retries=1):
        self.client = client
        self.timeout_ms = timeout_ms
        self.retries = retries

    async def classify(self, message):
        """Classify a preprocessed message."""
        import asyncio

        # Handle None text
        text = message.text
        if text is None:
            text = ""
        text = str(text).strip()

        if not text:
            return ResultFactory.create_result(
                intent="fallback",
                confidence=0.0,
                entities={},
                routing_hint=None,
            )

        # Build prompt with context
        prompt = self._build_prompt(message)

        # Retry logic for transient errors
        response = None
        last_error = None

        for attempt in range(self.retries + 1):
            try:
                # Call Gemini with timeout
                response = await asyncio.wait_for(
                    self.client.classify(prompt), timeout=self.timeout_ms / 1000.0
                )
                break
            except asyncio.TimeoutError as e:
                last_error = "Timeout error"  # TimeoutError has empty str()
                if attempt < self.retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                continue
            except ConnectionError as e:
                last_error = e
                if attempt < self.retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                continue
            except Exception as e:
                # Non-transient errors don't retry
                last_error = e
                break

        if response is None:
            # All attempts failed - return fallback
            result = ResultFactory.create_result(
                intent="fallback",
                confidence=0.0,
                entities={},
                routing_hint=None,
            )
            # Add error information if available
            if last_error:
                result.error = str(last_error)
            return result

        # Normalize confidence
        try:
            confidence = float(response.get("confidence", 0.0))
        except (ValueError, TypeError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        # Convert to ClassificationResult
        result = ResultFactory.create_result(
            intent=response.get("intent", "fallback"),
            confidence=confidence,
            entities=response.get("entities", {}),
            routing_hint=response.get("routing_hint"),
        )

        return result

    def _build_prompt(self, message) -> str:
        """Build classification prompt from message."""
        prompt_parts = []

        # Add history if present
        if message.history:
            prompt_parts.append("Histórico:")
            for turn in message.history[-3:]:  # Last 3 turns
                prompt_parts.append(f"{turn.role}: {turn.text}")

        # Add current message
        prompt_parts.append(f"Mensagem atual: {message.text}")

        # Add classification instruction
        prompt_parts.append(
            "\nClassifique em: greeting, information_request, "
            "qualification, scheduling ou fallback. "
            "Retorne JSON com intent, confidence e entities."
        )

        return "\n".join(prompt_parts)


@pytest.fixture
def orchestrator(gemini_stub):
    """Create orchestrator with stub."""
    return GeminiOrchestrator(client=gemini_stub, timeout_ms=120, retries=1)


# CONTRACT TESTS


@pytest.mark.asyncio
async def test_contract_basic_classification(orchestrator, base_msg, gemini_stub):
    """Test basic contract: receives PreprocessedMessage, returns ClassificationResult."""
    # Given
    gemini_stub.set_response("greeting", 0.9)

    # When
    result = await orchestrator.classify(base_msg)

    # Then
    assert result.intent == "greeting"
    assert result.confidence >= 0.8
    assert isinstance(result.entities, dict)
    assert not hasattr(result, "generated_text"), "Should not generate text"


@pytest.mark.asyncio
async def test_contract_returns_classification_not_text(
    orchestrator, base_msg, gemini_stub
):
    """Test that orchestrator never returns generated text, only classification."""
    # Given
    gemini_stub.next_response = {
        "intent": "information_request",
        "confidence": 0.85,
        "entities": {"topic": "pricing"},
        "generated_text": "This should not be returned",  # Should be ignored
    }

    # When
    result = await orchestrator.classify(base_msg)

    # Then
    assert result.intent == "information_request"
    assert not hasattr(result, "generated_text")
    assert "generated_text" not in result.__dict__


@pytest.mark.asyncio
async def test_contract_intent_enum_values(orchestrator, gemini_stub):
    """Test that all valid intent values are handled correctly."""
    valid_intents = [
        "greeting",
        "information_request",
        "qualification",
        "scheduling",
        "fallback",
    ]

    for intent in valid_intents:
        # Given
        msg = MessageFactory.create_simple_message(text=f"test {intent}")
        gemini_stub.set_response(intent, 0.8)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert result.intent == intent
        assert result.intent in valid_intents


@pytest.mark.asyncio
async def test_contract_confidence_range(orchestrator, base_msg, gemini_stub):
    """Test that confidence is always between 0.0 and 1.0."""
    test_confidences = [0.0, 0.25, 0.5, 0.75, 0.99, 1.0]

    for confidence in test_confidences:
        # Given
        gemini_stub.set_response("greeting", confidence)

        # When
        result = await orchestrator.classify(base_msg)

        # Then
        assert 0.0 <= result.confidence <= 1.0
        assert result.confidence == confidence


@pytest.mark.asyncio
async def test_contract_entities_always_dict(orchestrator, gemini_stub):
    """Test that entities is always a dict, even when empty."""
    # Test with empty entities
    msg1 = MessageFactory.create_simple_message(text="olá")
    gemini_stub.set_response("greeting", 0.9, entities={})
    result1 = await orchestrator.classify(msg1)
    assert isinstance(result1.entities, dict)
    assert len(result1.entities) == 0

    # Test with populated entities
    msg2 = MessageFactory.create_simple_message(text="qual o preço?")
    gemini_stub.set_response(
        "information_request", 0.85, entities={"topic": "pricing", "urgency": "low"}
    )
    result2 = await orchestrator.classify(msg2)
    assert isinstance(result2.entities, dict)
    assert result2.entities["topic"] == "pricing"
    assert result2.entities["urgency"] == "low"


@pytest.mark.asyncio
async def test_contract_routing_hint_optional(orchestrator, gemini_stub):
    """Test that routing_hint is optional but preserved when present."""
    # Without routing hint
    msg1 = MessageFactory.create_simple_message(text="bom dia")
    gemini_stub.set_response("greeting", 0.95)
    result1 = await orchestrator.classify(msg1)
    assert result1.routing_hint is None

    # With routing hint
    msg2 = MessageFactory.create_simple_message(text="ok")
    gemini_stub.set_response("fallback", 0.4, routing_hint="request_clarification")
    result2 = await orchestrator.classify(msg2)
    assert result2.routing_hint == "request_clarification"


@pytest.mark.asyncio
async def test_contract_handles_all_message_fields(orchestrator, gemini_stub):
    """Test that orchestrator handles all PreprocessedMessage fields correctly."""
    # Given - message with all fields populated
    msg = MessageFactory.create_simple_message(
        text="teste completo",
        phone="5511999999999",
        message_id="MSG_FULL_001",
        instance="test-instance",
        trace_id="TRACE_FULL",
        turn_id="TURN_FULL",
        sanitized=True,
        rate_limited=False,
        headers={"x-forwarded-for": "1.2.3.4", "user-agent": "test"},
    )
    gemini_stub.set_response("information_request", 0.75)

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.confidence == 0.75
    # Verify Gemini was called (message was processed)
    assert gemini_stub.call_count == 1


@pytest.mark.asyncio
async def test_contract_preserves_message_immutability(orchestrator, gemini_stub):
    """Test that orchestrator doesn't modify the input message."""
    # Given
    original_text = "mensagem original"
    msg = MessageFactory.create_simple_message(text=original_text)
    original_history_len = len(msg.history)

    gemini_stub.set_response("information_request", 0.8)

    # When
    await orchestrator.classify(msg)

    # Then - message should be unchanged
    assert msg.text == original_text
    assert len(msg.history) == original_history_len
    assert msg.phone == "555199999999"


@pytest.mark.asyncio
async def test_contract_processes_empty_text(orchestrator, gemini_stub):
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
async def test_contract_processes_very_long_text(orchestrator, gemini_stub):
    """Test that very long text is handled properly."""
    # Given - 2000 character message
    long_text = "muito " * 400
    msg = MessageFactory.create_simple_message(text=long_text)
    gemini_stub.set_response("information_request", 0.7)

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.confidence == 0.7


@pytest.mark.asyncio
async def test_contract_handles_special_characters(orchestrator, gemini_stub):
    """Test that special characters and emojis are handled."""
    special_texts = [
        "Olá! 😊 Como vai?",
        "R$ 100,00 por mês?",
        "email@example.com",
        "https://kumon.com.br",
        "Matemática & Português",
        '{"json": "test"}',
    ]

    for text in special_texts:
        # Given
        msg = MessageFactory.create_simple_message(text=text)
        gemini_stub.set_response("information_request", 0.8)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert result.intent is not None
        assert 0.0 <= result.confidence <= 1.0
