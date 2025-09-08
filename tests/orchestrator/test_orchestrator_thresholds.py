"""
Threshold and confidence tests for Gemini Orchestrator.
Tests confidence levels, ambiguity handling, and routing hints.
"""
import pytest

from tests.helpers.factories import MessageFactory
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


@pytest.fixture
def orchestrator(threshold_aware_gemini_stub):
    """Create orchestrator with threshold-aware stub."""
    return GeminiOrchestrator(
        client=threshold_aware_gemini_stub, timeout_ms=120, retries=1
    )


# HIGH CONFIDENCE TESTS (>= 0.8)


@pytest.mark.asyncio
async def test_threshold_high_confidence_greeting(
    orchestrator, threshold_aware_gemini_stub
):
    """Test high confidence classification for clear greetings."""
    greetings = ["olá", "bom dia", "boa tarde", "oi, tudo bem?"]

    for greeting in greetings:
        # Given
        msg = MessageFactory.create_simple_message(text=greeting)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert result.confidence >= 0.8, f"Low confidence for '{greeting}'"
        assert result.intent == "greeting"
        assert result.routing_hint is None  # High confidence doesn't need hints


@pytest.mark.asyncio
async def test_threshold_high_confidence_qualification(
    orchestrator, threshold_aware_gemini_stub
):
    """Test high confidence for clear qualification intents."""
    # Given
    msg = MessageFactory.create_simple_message(text="quero matricular meu filho")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence >= 0.8
    assert result.intent == "qualification"
    assert result.routing_hint is None


@pytest.mark.asyncio
async def test_threshold_high_confidence_information(
    orchestrator, threshold_aware_gemini_stub
):
    """Test high confidence for clear information requests."""
    # Given
    msg = MessageFactory.create_simple_message(text="qual o preço da mensalidade?")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence >= 0.8
    assert result.intent == "information_request"


# MEDIUM CONFIDENCE TESTS (0.5 - 0.79)


@pytest.mark.asyncio
async def test_threshold_medium_confidence_vague_info(
    orchestrator, threshold_aware_gemini_stub
):
    """Test medium confidence for vague information requests."""
    # Given
    msg = MessageFactory.create_simple_message(text="informações")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert 0.5 <= result.confidence < 0.8
    assert result.intent == "information_request"
    assert result.routing_hint == "confirm_intent"  # Medium confidence hint


@pytest.mark.asyncio
async def test_threshold_medium_confidence_unclear_intent(
    orchestrator, threshold_aware_gemini_stub
):
    """Test medium confidence for unclear intentions."""
    # Given
    msg = MessageFactory.create_simple_message(text="como funciona")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert 0.5 <= result.confidence < 0.8
    assert result.intent == "information_request"
    assert result.routing_hint == "confirm_intent"


@pytest.mark.asyncio
async def test_threshold_medium_confidence_ambiguous_scheduling(
    orchestrator, threshold_aware_gemini_stub
):
    """Test medium confidence for ambiguous scheduling."""
    # Given - "pode ser" without context
    msg = MessageFactory.create_simple_message(text="pode ser")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert 0.5 <= result.confidence < 0.8
    assert result.routing_hint in ["confirm_intent", "request_clarification"]


# LOW CONFIDENCE TESTS (< 0.5)


@pytest.mark.asyncio
async def test_threshold_low_confidence_triggers_fallback(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that low confidence triggers fallback intent."""
    ambiguous = ["ok", "sim", "legal", "entendi"]

    for text in ambiguous:
        # Given
        msg = MessageFactory.create_simple_message(text=text)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert result.confidence < 0.5, f"High confidence for ambiguous '{text}'"
        assert result.intent == "fallback"
        assert result.routing_hint == "request_clarification"


@pytest.mark.asyncio
async def test_threshold_single_word_responses(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that single word responses have appropriate confidence."""
    test_cases = [
        ("sim", "fallback", 0.42),  # Ambiguous
        ("não", "fallback", 0.35),  # Ambiguous
        ("olá", "greeting", 0.95),  # Clear greeting
        ("informações", "information_request", 0.72),  # Somewhat clear
    ]

    for text, expected_intent, _ in test_cases:
        # Given
        msg = MessageFactory.create_simple_message(text=text)

        # When
        result = await orchestrator.classify(msg)

        # Then
        if expected_intent == "fallback":
            assert result.confidence < 0.5
            assert result.routing_hint == "request_clarification"
        elif expected_intent == "greeting":
            assert result.confidence >= 0.8
        else:
            assert 0.5 <= result.confidence < 0.8


# ROUTING HINT TESTS


@pytest.mark.asyncio
async def test_threshold_routing_hint_for_clarification(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that ambiguous messages get clarification routing hint."""
    # Given
    msg = MessageFactory.create_simple_message(text="legal")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence < 0.5
    assert result.routing_hint == "request_clarification"
    assert result.intent == "fallback"


@pytest.mark.asyncio
async def test_threshold_routing_hint_for_confirmation(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that medium confidence gets confirmation routing hint."""
    # Given
    msg = MessageFactory.create_simple_message(text="informações sobre o curso")

    threshold_aware_gemini_stub.confidence_map["informações"] = 0.65

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert 0.5 <= result.confidence < 0.7
    assert result.routing_hint == "confirm_intent"


@pytest.mark.asyncio
async def test_threshold_no_routing_hint_high_confidence(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that high confidence doesn't need routing hints."""
    # Given
    msg = MessageFactory.create_simple_message(text="bom dia")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence >= 0.8
    assert result.routing_hint is None


# CONFIDENCE BOUNDARY TESTS


@pytest.mark.asyncio
async def test_threshold_boundary_exactly_08(orchestrator, threshold_aware_gemini_stub):
    """Test boundary condition at exactly 0.8 confidence."""
    # Given
    threshold_aware_gemini_stub.next_response = {
        "intent": "information_request",
        "confidence": 0.8,
        "entities": {},
    }
    msg = MessageFactory.create_simple_message(text="test boundary")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence == 0.8
    assert result.routing_hint is None  # 0.8 is high confidence


@pytest.mark.asyncio
async def test_threshold_boundary_exactly_05(orchestrator, threshold_aware_gemini_stub):
    """Test boundary condition at exactly 0.5 confidence."""
    # Given
    threshold_aware_gemini_stub.next_response = {
        "intent": "information_request",
        "confidence": 0.5,
        "entities": {},
        "routing_hint": "confirm_intent",
    }
    msg = MessageFactory.create_simple_message(text="test boundary")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence == 0.5
    assert result.intent == "information_request"  # Still classified, not fallback
    assert result.routing_hint == "confirm_intent"


# AMBIGUITY RESOLUTION TESTS


@pytest.mark.asyncio
async def test_threshold_ambiguous_without_context(
    orchestrator, threshold_aware_gemini_stub
):
    """Test ambiguous message without context triggers fallback."""
    # Given - no context
    msg = MessageFactory.create_simple_message(text="amanhã")

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence < 0.5
    assert result.intent == "fallback"
    assert result.routing_hint == "request_clarification"


@pytest.mark.asyncio
async def test_threshold_ambiguous_with_context(orchestrator):
    """Test ambiguous message with context gets higher confidence."""
    # Given - with scheduling context
    msg = MessageFactory.create_with_history(
        text="amanhã",
        history_turns=[
            ("user", "Quero agendar visita"),
            ("assistant", "Quando prefere?"),
        ],
    )

    # Mock higher confidence due to context
    orchestrator.client.next_response = {
        "intent": "scheduling",
        "confidence": 0.75,  # Higher with context
        "entities": {"day": "tomorrow"},
    }

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.confidence >= 0.7
    assert result.intent == "scheduling"


# CONFIDENCE DISTRIBUTION TESTS


@pytest.mark.asyncio
async def test_threshold_confidence_distribution(
    orchestrator, threshold_aware_gemini_stub
):
    """Test that confidence distribution makes sense across different inputs."""
    test_cases = [
        # (text, min_confidence, max_confidence)
        ("olá", 0.9, 1.0),  # Very clear
        ("bom dia", 0.9, 1.0),  # Very clear
        ("informações", 0.6, 0.8),  # Somewhat clear
        ("como funciona", 0.6, 0.8),  # Somewhat clear
        ("pode ser", 0.4, 0.6),  # Ambiguous
        ("ok", 0.3, 0.5),  # Very ambiguous
        ("sim", 0.3, 0.5),  # Very ambiguous
    ]

    for text, min_conf, max_conf in test_cases:
        # Given
        msg = MessageFactory.create_simple_message(text=text)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert (
            min_conf <= result.confidence <= max_conf
        ), f"Confidence {result.confidence} out of range [{min_conf}, {max_conf}] for '{text}'"
