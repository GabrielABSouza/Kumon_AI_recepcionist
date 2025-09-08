"""
Context understanding tests for Gemini Orchestrator.
Tests pronoun resolution, topic continuation, and context-aware classification.
"""
import pytest

from tests.helpers.factories import MessageFactory
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


@pytest.fixture
def orchestrator(context_aware_gemini_stub):
    """Create orchestrator with context-aware stub."""
    return GeminiOrchestrator(
        client=context_aware_gemini_stub, timeout_ms=120, retries=1
    )


# PRONOUN RESOLUTION TESTS


@pytest.mark.asyncio
async def test_context_pronoun_resolution_ele(orchestrator, context_aware_gemini_stub):
    """Test pronoun 'ele' resolution with pricing context."""
    # Given - history about pricing
    msg = MessageFactory.create_with_history(
        text="e ele inclui material?",
        history_turns=[
            ("user", "Quais os preços do Kumon?"),
            ("assistant", "Temos planos a partir de R$ 280 mensais."),
        ],
    )

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.entities.get("topic") == "pricing"
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_context_pronoun_resolution_isso(orchestrator, context_aware_gemini_stub):
    """Test pronoun 'isso' resolution with method context."""
    # Given - history about method
    msg = MessageFactory.create_with_history(
        text="isso funciona mesmo?",
        history_turns=[
            ("user", "Como é o método Kumon?"),
            (
                "assistant",
                "O método Kumon desenvolve autodidatismo através de exercícios progressivos.",
            ),
        ],
    )

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.entities.get("topic") == "method"
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_context_pronoun_without_history(orchestrator, context_aware_gemini_stub):
    """Test that pronouns without context trigger fallback."""
    # Given - no history
    msg = MessageFactory.create_simple_message(text="ele é bom?")

    # When
    result = await orchestrator.classify(msg)

    # Then - should be uncertain without context
    assert result.confidence < 0.8  # Not high confidence
    assert result.intent in ["fallback", "information_request"]


# TOPIC CONTINUATION TESTS


@pytest.mark.asyncio
async def test_context_topic_continuation_pricing(
    orchestrator, context_aware_gemini_stub
):
    """Test continuation of pricing topic."""
    # Given - discussing pricing
    msg = MessageFactory.create_with_history(
        text="e o horário de pagamento?",
        history_turns=[
            ("user", "Quanto custa a mensalidade?"),
            ("assistant", "O valor é R$ 280 por disciplina."),
        ],
    )

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    # Should understand it's still about pricing/payment
    assert (
        "pric" in str(result.entities).lower() or "pay" in str(result.entities).lower()
    )


@pytest.mark.asyncio
async def test_context_topic_continuation_scheduling(
    orchestrator, context_aware_gemini_stub
):
    """Test continuation of scheduling topic."""
    # Given - discussing visit
    msg = MessageFactory.create_with_history(
        text="pode ser de manhã?",
        history_turns=[
            ("user", "Quero agendar uma visita"),
            ("assistant", "Claro! Quando você prefere?"),
        ],
    )

    context_aware_gemini_stub.set_response(
        "scheduling", 0.88, {"time_preference": "morning", "continuation": True}
    )

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "scheduling"
    assert result.confidence >= 0.85


@pytest.mark.asyncio
async def test_context_topic_switch(orchestrator, context_aware_gemini_stub):
    """Test detection of topic switch."""
    # Given - was discussing pricing, now asking about location
    msg = MessageFactory.create_with_history(
        text="onde fica a unidade?",
        history_turns=[
            ("user", "Qual o valor?"),
            ("assistant", "R$ 280 mensais."),
        ],
    )

    context_aware_gemini_stub.set_response(
        "information_request", 0.9, {"topic": "location", "topic_switch": True}
    )

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "information_request"
    assert result.entities.get("topic") == "location"


# OBJECTION HANDLING TESTS


@pytest.mark.asyncio
async def test_context_objection_after_pricing(orchestrator, context_aware_gemini_stub):
    """Test objection detection after pricing information."""
    # Given - just received pricing
    msg = MessageFactory.create_with_history(
        text="achei caro, tem desconto?",
        history_turns=[
            ("user", "Quanto custa?"),
            ("assistant", "O valor é R$ 280 por mês."),
        ],
    )

    context_aware_gemini_stub.next_response = {
        "intent": "objection",
        "confidence": 0.75,
        "entities": {"topic": "pricing", "seeking": "discount"},
        "routing_hint": "handle_price_objection",
    }

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "objection"
    assert result.entities.get("topic") == "pricing"
    assert result.routing_hint == "handle_price_objection"


@pytest.mark.asyncio
async def test_context_objection_location(orchestrator, context_aware_gemini_stub):
    """Test location objection detection."""
    # Given - discussing location
    msg = MessageFactory.create_with_history(
        text="muito longe pra mim",
        history_turns=[
            ("user", "Onde fica?"),
            ("assistant", "Estamos na Rua Example, 123, Centro."),
        ],
    )

    context_aware_gemini_stub.next_response = {
        "intent": "objection",
        "confidence": 0.8,
        "entities": {"topic": "location", "issue": "distance"},
    }

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "objection"
    assert result.entities.get("topic") == "location"


# LANGUAGE VARIATION TESTS


@pytest.mark.asyncio
async def test_context_handles_informal_language(
    orchestrator, context_aware_gemini_stub
):
    """Test handling of informal Portuguese."""
    informal_messages = [
        "vc tem matemática?",
        "qto custa?",
        "td bem, queria infos",
        "blz, vou pensar",
        "pq esse método?",
    ]

    for text in informal_messages:
        # Given
        msg = MessageFactory.create_simple_message(text=text)
        context_aware_gemini_stub.set_response("information_request", 0.7)

        # When
        result = await orchestrator.classify(msg)

        # Then - should still classify correctly
        assert result.intent in [
            "information_request",
            "greeting",
            "qualification",
            "scheduling",
            "fallback",
        ]
        assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_context_handles_typos(orchestrator, context_aware_gemini_stub):
    """Test handling of common typos."""
    typo_messages = [
        ("ola", "greeting"),
        ("bao tarde", "greeting"),
        ("qero matricular", "qualification"),
        ("agnedar visita", "scheduling"),
    ]

    for text, expected_intent in typo_messages:
        # Given
        msg = MessageFactory.create_simple_message(text=text)
        context_aware_gemini_stub.set_response(expected_intent, 0.75)

        # When
        result = await orchestrator.classify(msg)

        # Then
        assert result.intent == expected_intent
        assert result.confidence >= 0.7


# MULTI-TURN CONTEXT TESTS


@pytest.mark.asyncio
async def test_context_uses_recent_history(orchestrator, context_aware_gemini_stub):
    """Test that only recent history is used (last 3 turns)."""
    # Given - long history
    history_turns = [
        ("user", "Oi"),  # Old - should be ignored
        ("assistant", "Olá!"),  # Old - should be ignored
        ("user", "Vocês têm português?"),  # Should be included
        ("assistant", "Sim, temos Português."),  # Should be included
        ("user", "E matemática?"),  # Should be included
        ("assistant", "Também temos Matemática."),  # Should be included
    ]

    msg = MessageFactory.create_with_history(
        text="qual o valor?", history_turns=history_turns
    )

    # When
    result = await orchestrator.classify(msg)

    # Then - should understand it's about pricing for the subjects discussed
    assert result.intent == "information_request"
    # Verify only last 3 turns were in prompt
    assert "Oi" not in context_aware_gemini_stub.last_prompt
    assert "matemática" in context_aware_gemini_stub.last_prompt.lower()


@pytest.mark.asyncio
async def test_context_handles_mixed_languages(orchestrator, context_aware_gemini_stub):
    """Test handling of code-switching (Portuguese + English)."""
    # Given
    msg = MessageFactory.create_simple_message(
        text="Preciso fazer um appointment para conhecer o method"
    )
    context_aware_gemini_stub.set_response("scheduling", 0.82, {"mixed_language": True})

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "scheduling"
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_context_confirmation_responses(orchestrator, context_aware_gemini_stub):
    """Test that confirmations use context to determine intent."""
    # Given - scheduling context
    msg = MessageFactory.create_with_history(
        text="pode ser",
        history_turns=[
            ("user", "Quero agendar visita"),
            ("assistant", "Que tal amanhã às 14h?"),
        ],
    )

    context_aware_gemini_stub.set_response("scheduling", 0.85, {"confirmation": True})

    # When
    result = await orchestrator.classify(msg)

    # Then
    assert result.intent == "scheduling"
    assert result.entities.get("confirmation") is True
    assert result.confidence >= 0.8
