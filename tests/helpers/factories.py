"""
Factory builders for test messages and states.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HistoryTurn:
    """Represents a single turn in conversation history."""

    role: str  # "user" or "assistant"
    text: str
    timestamp: Optional[float] = None


@dataclass
class PreprocessedMessage:
    """Message after preprocessing with all metadata."""

    phone: str
    text: str
    headers: Dict[str, str]
    from_me: bool = False
    history: List[HistoryTurn] = field(default_factory=list)
    message_id: Optional[str] = None
    instance: str = "recepcionistakumon"
    trace_id: Optional[str] = None
    turn_id: Optional[str] = None
    sanitized: bool = False
    rate_limited: bool = False


@dataclass
class ClassificationResult:
    """Result from Gemini orchestrator classification."""

    intent: str  # greeting, information_request, qualification, scheduling, fallback
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any] = field(default_factory=dict)
    routing_hint: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class MessageFactory:
    """Factory for creating test messages."""

    @staticmethod
    def create_simple_message(
        text: str = "olá", phone: str = "555199999999", **kwargs: Any
    ) -> PreprocessedMessage:
        """Create a simple preprocessed message."""
        return PreprocessedMessage(
            phone=phone,
            text=text,
            headers=kwargs.get("headers", {"x-forwarded-for": "1.2.3.4"}),
            from_me=kwargs.get("from_me", False),
            history=kwargs.get("history", []),
            message_id=kwargs.get("message_id", "MSG_TEST_001"),
            trace_id=kwargs.get("trace_id", "TRACE_001"),
            turn_id=kwargs.get("turn_id", "TURN_001"),
        )

    @staticmethod
    def create_with_history(
        text: str, history_turns: List[tuple], **kwargs
    ) -> PreprocessedMessage:
        """Create message with conversation history."""
        history = [HistoryTurn(role=role, text=txt) for role, txt in history_turns]
        return MessageFactory.create_simple_message(
            text=text, history=history, **kwargs
        )

    @staticmethod
    def create_ambiguous_message(**kwargs) -> PreprocessedMessage:
        """Create an ambiguous message that should trigger fallback."""
        ambiguous_texts = ["legal", "ok", "sim", "não", "pode ser"]
        import random

        text = kwargs.pop("text", random.choice(ambiguous_texts))
        return MessageFactory.create_simple_message(text=text, **kwargs)

    @staticmethod
    def create_greeting_variations() -> List[PreprocessedMessage]:
        """Create various greeting messages for testing."""
        greetings = [
            "oi",
            "olá",
            "ola",
            "bom dia",
            "boa tarde",
            "boa noite",
            "Olá, tudo bem?",
            "oi, gostaria de informações",
        ]
        return [MessageFactory.create_simple_message(text=g) for g in greetings]

    @staticmethod
    def create_information_requests() -> List[PreprocessedMessage]:
        """Create various information request messages."""
        requests = [
            "quais são os preços?",
            "como funciona o método?",
            "qual o horário de funcionamento?",
            "vocês têm matemática?",
            "aceita cartão?",
            "onde fica a unidade?",
        ]
        return [MessageFactory.create_simple_message(text=r) for r in requests]

    @staticmethod
    def create_scheduling_messages() -> List[PreprocessedMessage]:
        """Create scheduling-related messages."""
        scheduling = [
            "quero agendar uma visita",
            "posso conhecer a escola?",
            "tem horário amanhã?",
            "queria marcar uma avaliação",
            "disponibilidade para visita",
        ]
        return [MessageFactory.create_simple_message(text=s) for s in scheduling]

    @staticmethod
    def create_qualification_messages() -> List[PreprocessedMessage]:
        """Create qualification/enrollment messages."""
        qualification = [
            "quero matricular meu filho",
            "como faço a matrícula?",
            "quais documentos preciso?",
            "minha filha tem 5 anos, pode?",
            "adulto pode fazer kumon?",
        ]
        return [MessageFactory.create_simple_message(text=q) for q in qualification]


class ResultFactory:
    """Factory for creating classification results."""

    @staticmethod
    def create_result(
        intent: str = "greeting", confidence: float = 0.9, **kwargs: Any
    ) -> ClassificationResult:
        """Create a classification result."""
        return ClassificationResult(
            intent=intent,
            confidence=confidence,
            entities=kwargs.get("entities", {}),
            routing_hint=kwargs.get("routing_hint"),
            latency_ms=kwargs.get("latency_ms", 50.0),
            error=kwargs.get("error"),
        )

    @staticmethod
    def create_high_confidence_result(intent: str) -> ClassificationResult:
        """Create a high confidence result (>=0.8)."""
        return ResultFactory.create_result(intent=intent, confidence=0.92)

    @staticmethod
    def create_medium_confidence_result(intent: str) -> ClassificationResult:
        """Create a medium confidence result (0.5-0.79)."""
        return ResultFactory.create_result(intent=intent, confidence=0.65)

    @staticmethod
    def create_low_confidence_result() -> ClassificationResult:
        """Create a low confidence fallback result."""
        return ResultFactory.create_result(
            intent="fallback",
            confidence=0.35,
            routing_hint="request_clarification",
        )

    @staticmethod
    def create_error_result(error: str = "timeout") -> ClassificationResult:
        """Create an error result."""
        return ResultFactory.create_result(
            intent="fallback", confidence=0.0, error=error
        )
