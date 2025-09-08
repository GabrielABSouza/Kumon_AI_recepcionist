"""
Phase 1 - Basic Node Execution Tests
Tests isolated node execution with Portuguese language enforcement.
"""
from dataclasses import dataclass
from typing import Any, Dict

import pytest


@dataclass
class NodeResponse:
    """Response from a LangGraph node."""

    response_text: str
    stage_update: str
    metadata: Dict[str, Any]
    language: str = "pt-br"


@dataclass
class ConversationState:
    """Conversation state for LangGraph."""

    conversation_id: str
    stage: str
    context: Dict[str, Any]
    entities: Dict[str, Any]
    language: str = "pt-br"


class NodeExecutor:
    """Base class for node executors."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute node logic and return response."""
        raise NotImplementedError


class GreetingNode(NodeExecutor):
    """Greeting node executor."""

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute greeting logic."""
        # For testing, use stub response
        if self.llm_client:
            response = await self.llm_client.generate("greeting", state.context)
        else:
            response = "Olá! Seja bem-vindo ao Kumon. Como posso ajudá-lo hoje?"

        return NodeResponse(
            response_text=response,
            stage_update="qualification",
            metadata={"node": "greeting", "transition": "greeting->qualification"},
            language="pt-br",
        )


class InformationNode(NodeExecutor):
    """Information request node executor."""

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute information logic."""
        topic = state.entities.get("topic", "geral")

        if self.llm_client:
            response = await self.llm_client.generate("information", {"topic": topic})
        else:
            responses = {
                "preço": "A mensalidade do Kumon varia conforme a unidade. Posso agendar uma visita para você conhecer nossa unidade e receber todas as informações?",
                "método": "O método Kumon desenvolve o autodidatismo através de material individualizado. Gostaria de agendar uma avaliação diagnóstica gratuita?",
                "horário": "Nossas aulas acontecem duas vezes por semana. Os horários específicos posso informar durante sua visita. Posso agendar?",
                "geral": "O Kumon é um método de estudo individualizado. Posso explicar melhor em uma visita. Gostaria de agendar?",
            }
            response = responses.get(topic, responses["geral"])

        # Stay in information stage unless moving to scheduling
        next_stage = (
            "information" if "agendar" not in input_text.lower() else "scheduling"
        )

        return NodeResponse(
            response_text=response,
            stage_update=next_stage,
            metadata={"node": "information", "topic": topic},
            language="pt-br",
        )


class QualificationNode(NodeExecutor):
    """Qualification node executor."""

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute qualification logic."""
        if self.llm_client:
            response = await self.llm_client.generate("qualification", state.context)
        else:
            # Check what info we need
            missing = []
            if "student_name" not in state.entities:
                missing.append("nome do aluno")
            if "student_age" not in state.entities:
                missing.append("idade")
            if "subject" not in state.entities:
                missing.append("matéria de interesse")

            if missing:
                response = f"Para prosseguir, preciso de algumas informações: {', '.join(missing)}."
            else:
                response = "Ótimo! Já tenho as informações necessárias. Vamos agendar sua visita?"

        next_stage = "qualification" if missing else "scheduling"

        return NodeResponse(
            response_text=response,
            stage_update=next_stage,
            metadata={
                "node": "qualification",
                "missing_fields": missing if missing else [],
            },
            language="pt-br",
        )


class SchedulingNode(NodeExecutor):
    """Scheduling node executor."""

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute scheduling logic."""
        if self.llm_client:
            response = await self.llm_client.generate("scheduling", state.context)
        else:
            response = "Perfeito! Temos horários disponíveis na terça e quinta às 14h ou 16h. Qual prefere?"

        return NodeResponse(
            response_text=response,
            stage_update="scheduling",
            metadata={"node": "scheduling", "awaiting": "time_preference"},
            language="pt-br",
        )


class FallbackNode(NodeExecutor):
    """Fallback node executor."""

    async def execute(self, state: ConversationState, input_text: str) -> NodeResponse:
        """Execute fallback logic."""
        if self.llm_client:
            response = await self.llm_client.generate("fallback", state.context)
        else:
            response = "Desculpe, não entendi. Você gostaria de saber sobre o método Kumon, valores ou agendar uma visita?"

        # Fallback stays in current stage
        return NodeResponse(
            response_text=response,
            stage_update=state.stage,  # Keep current stage
            metadata={"node": "fallback", "reason": "unclear_intent"},
            language="pt-br",
        )


class LanguageEnforcer:
    """Enforces Portuguese language in responses."""

    @staticmethod
    def is_portuguese(text: str) -> bool:
        """Check if text is in Portuguese."""
        if not text:
            return False

        # Simple heuristic - check for Portuguese-specific patterns
        pt_indicators = [
            "ção",
            "ões",
            "ão",
            "ã",
            "õ",
            "nh",
            "lh",
            "você",
            "não",
            "é",
            "está",
            "olá",
            "obrigad",
            "como",
            "posso",
            "ajudar",
            "hoje",
            "bem-vindo",
            "gostaria",
            "pode",
            "para",
            "com",
            "nosso",
            "nossa",
            "terça",
            "quinta",
            "horário",
            "disponível",
            "às",
            "ou",
            "qual",
        ]

        text_lower = text.lower()

        # Check for English indicators (should not be present as whole words)
        en_indicators = [
            "the",
            "is",
            "are",
            "you",
            "hello",
            "thanks",
            "please",
            "can",
            "help",
            "how",
        ]
        en_count = 0
        for indicator in en_indicators:
            # Check for whole word matches
            import re

            if re.search(r"\b" + indicator + r"\b", text_lower):
                en_count += 1

        # If too many English words, it's not Portuguese
        if en_count >= 3:
            return False

        # Check for Portuguese indicators
        pt_count = sum(1 for ind in pt_indicators if ind in text_lower)

        # More lenient: 1 Portuguese indicator is enough for texts over 20 chars
        # or any Portuguese indicator for shorter texts
        return pt_count >= 1

    @staticmethod
    def enforce_portuguese(text: str) -> str:
        """Force text to Portuguese if not already."""
        if LanguageEnforcer.is_portuguese(text):
            return text

        # Fallback to a generic Portuguese response
        return "Desculpe, houve um erro. Por favor, tente novamente ou entre em contato conosco."


# Test fixtures
@pytest.fixture
def greeting_node():
    """Create greeting node."""
    return GreetingNode()


@pytest.fixture
def information_node():
    """Create information node."""
    return InformationNode()


@pytest.fixture
def qualification_node():
    """Create qualification node."""
    return QualificationNode()


@pytest.fixture
def scheduling_node():
    """Create scheduling node."""
    return SchedulingNode()


@pytest.fixture
def fallback_node():
    """Create fallback node."""
    return FallbackNode()


@pytest.fixture
def base_state():
    """Create base conversation state."""
    return ConversationState(
        conversation_id="test_123",
        stage="greeting",
        context={},
        entities={},
        language="pt-br",
    )


@pytest.fixture
def language_enforcer():
    """Create language enforcer."""
    return LanguageEnforcer()


# PHASE 1 TESTS - Basic Node Execution


@pytest.mark.asyncio
async def test_greeting_node_returns_portuguese(greeting_node, base_state):
    """Test that greeting node returns Portuguese response."""
    # When
    response = await greeting_node.execute(base_state, "hello")

    # Then
    assert response.response_text
    assert response.language == "pt-br"
    assert LanguageEnforcer.is_portuguese(response.response_text)
    assert (
        "olá" in response.response_text.lower()
        or "bem-vindo" in response.response_text.lower()
    )


@pytest.mark.asyncio
async def test_greeting_node_updates_stage(greeting_node, base_state):
    """Test that greeting node updates stage correctly."""
    # When
    response = await greeting_node.execute(base_state, "oi")

    # Then
    assert response.stage_update == "qualification"
    assert response.metadata["transition"] == "greeting->qualification"


@pytest.mark.asyncio
async def test_information_node_returns_portuguese(information_node, base_state):
    """Test that information node returns Portuguese response."""
    # Given
    base_state.stage = "information"
    base_state.entities = {"topic": "preço"}

    # When
    response = await information_node.execute(base_state, "quanto custa?")

    # Then
    assert response.response_text
    assert response.language == "pt-br"
    assert LanguageEnforcer.is_portuguese(response.response_text)
    assert (
        "mensalidade" in response.response_text.lower()
        or "valor" in response.response_text.lower()
    )


@pytest.mark.asyncio
async def test_information_node_stays_in_stage(information_node, base_state):
    """Test that information node stays in stage for follow-up questions."""
    # Given
    base_state.stage = "information"
    base_state.entities = {"topic": "método"}

    # When
    response = await information_node.execute(base_state, "como funciona?")

    # Then
    assert response.stage_update == "information"  # Stays in information
    assert response.metadata["topic"] == "método"


@pytest.mark.asyncio
async def test_information_node_transitions_to_scheduling(information_node, base_state):
    """Test that information node transitions to scheduling when appropriate."""
    # Given
    base_state.stage = "information"
    base_state.entities = {"topic": "preço"}

    # When
    response = await information_node.execute(
        base_state, "sim, quero agendar uma visita"
    )

    # Then
    assert response.stage_update == "scheduling"


@pytest.mark.asyncio
async def test_qualification_node_returns_portuguese(qualification_node, base_state):
    """Test that qualification node returns Portuguese response."""
    # Given
    base_state.stage = "qualification"

    # When
    response = await qualification_node.execute(base_state, "meu filho tem 8 anos")

    # Then
    assert response.response_text
    assert response.language == "pt-br"
    assert LanguageEnforcer.is_portuguese(response.response_text)


@pytest.mark.asyncio
async def test_qualification_node_collects_missing_fields(
    qualification_node, base_state
):
    """Test that qualification node identifies missing fields."""
    # Given
    base_state.stage = "qualification"
    base_state.entities = {"student_age": 8}

    # When
    response = await qualification_node.execute(base_state, "8 anos")

    # Then
    assert response.stage_update == "qualification"  # Stay in qualification
    assert "missing_fields" in response.metadata
    assert "nome do aluno" in response.response_text
    assert "matéria de interesse" in response.response_text


@pytest.mark.asyncio
async def test_qualification_node_transitions_when_complete(
    qualification_node, base_state
):
    """Test that qualification transitions to scheduling when info is complete."""
    # Given
    base_state.stage = "qualification"
    base_state.entities = {
        "student_name": "João",
        "student_age": 8,
        "subject": "matemática",
    }

    # When
    response = await qualification_node.execute(base_state, "matemática")

    # Then
    assert response.stage_update == "scheduling"
    assert response.metadata["missing_fields"] == []


@pytest.mark.asyncio
async def test_scheduling_node_returns_portuguese(scheduling_node, base_state):
    """Test that scheduling node returns Portuguese response."""
    # Given
    base_state.stage = "scheduling"

    # When
    response = await scheduling_node.execute(base_state, "quero agendar")

    # Then
    assert response.response_text
    assert response.language == "pt-br"
    assert LanguageEnforcer.is_portuguese(response.response_text)
    assert (
        "horário" in response.response_text.lower()
        or "disponível" in response.response_text.lower()
    )


@pytest.mark.asyncio
async def test_scheduling_node_stays_in_stage(scheduling_node, base_state):
    """Test that scheduling node stays in scheduling stage."""
    # Given
    base_state.stage = "scheduling"

    # When
    response = await scheduling_node.execute(base_state, "terça às 14h")

    # Then
    assert response.stage_update == "scheduling"
    assert response.metadata["awaiting"] == "time_preference"


@pytest.mark.asyncio
async def test_fallback_node_returns_portuguese(fallback_node, base_state):
    """Test that fallback node returns Portuguese response."""
    # Given
    base_state.stage = "information"

    # When
    response = await fallback_node.execute(base_state, "asdkfjaslkdfj")

    # Then
    assert response.response_text
    assert response.language == "pt-br"
    assert LanguageEnforcer.is_portuguese(response.response_text)
    assert (
        "desculpe" in response.response_text.lower()
        or "não entendi" in response.response_text.lower()
    )


@pytest.mark.asyncio
async def test_fallback_node_preserves_current_stage(fallback_node, base_state):
    """Test that fallback preserves the current stage."""
    # Given
    base_state.stage = "qualification"

    # When
    response = await fallback_node.execute(base_state, "????")

    # Then
    assert response.stage_update == "qualification"  # Stays in current stage
    assert response.metadata["reason"] == "unclear_intent"


@pytest.mark.asyncio
async def test_language_enforcer_detects_portuguese(language_enforcer):
    """Test that language enforcer correctly detects Portuguese."""
    # Portuguese texts
    pt_texts = [
        "Olá, como você está?",
        "A mensalidade é de R$ 500,00",
        "Não entendi sua pergunta",
        "Obrigado pela informação",
    ]

    for text in pt_texts:
        assert language_enforcer.is_portuguese(text), f"Failed to detect PT: {text}"


@pytest.mark.asyncio
async def test_language_enforcer_detects_english(language_enforcer):
    """Test that language enforcer correctly detects English."""
    # English texts
    en_texts = [
        "Hello, how are you?",
        "The price is $500",
        "I don't understand",
        "Thanks for the information",
    ]

    for text in en_texts:
        assert not language_enforcer.is_portuguese(text), f"Failed to detect EN: {text}"


@pytest.mark.asyncio
async def test_language_enforcer_forces_portuguese(language_enforcer):
    """Test that language enforcer forces Portuguese when needed."""
    # Given
    english_text = "Hello, this is the Kumon method"

    # When
    result = language_enforcer.enforce_portuguese(english_text)

    # Then
    assert language_enforcer.is_portuguese(result)
    assert "desculpe" in result.lower()


@pytest.mark.asyncio
async def test_all_nodes_return_portuguese():
    """Test that all nodes return Portuguese responses."""
    # Create all nodes
    nodes = [
        GreetingNode(),
        InformationNode(),
        QualificationNode(),
        SchedulingNode(),
        FallbackNode(),
    ]

    base_state = ConversationState(
        conversation_id="test_all",
        stage="greeting",
        context={},
        entities={"topic": "geral"},
        language="pt-br",
    )

    # Test each node
    for node in nodes:
        response = await node.execute(base_state, "test input")
        assert response.language == "pt-br"
        assert LanguageEnforcer.is_portuguese(response.response_text)
        assert response.stage_update is not None
