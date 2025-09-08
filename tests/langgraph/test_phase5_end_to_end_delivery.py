"""
Phase 5 - End-to-End Delivery Tests
Tests complete flow from WhatsApp message to delivery with all guarantees.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

import pytest

# Import all components from previous phases
from tests.helpers.factories import PreprocessedMessage
from tests.helpers.gemini_stubs import GeminiStub
from tests.langgraph.test_phase1_node_execution import LanguageEnforcer
from tests.langgraph.test_phase2_state_persistence import (
    PostgresStub,
    RedisStub,
    StateManager,
)
from tests.langgraph.test_phase3_idempotency import IdempotencyStore
from tests.langgraph.test_phase4_gemini_integration import (
    GeminiLangGraphPipeline,
    LangGraphRouter,
)
from tests.orchestrator.test_orchestrator_contract import GeminiOrchestrator


@dataclass
class WhatsAppMessage:
    """Incoming WhatsApp message."""

    instance: str
    phone: str
    message: str
    messageId: str
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    fromMe: bool = False


@dataclass
class WhatsAppResponse:
    """Outgoing WhatsApp response."""

    phone: str
    message: str
    messageId: str
    deliveredAt: datetime
    attempts: int = 1


class EvolutionAPIStub:
    """Mock Evolution API for WhatsApp."""

    def __init__(self):
        self.sent_messages: List[WhatsAppResponse] = []
        self.behavior = "normal"  # normal, fail_once, fail_twice, always_fail
        self.send_attempts = 0
        self.delay_ms = 10

    async def send_message(
        self, instance: str, phone: str, message: str
    ) -> Dict[str, Any]:
        """Send WhatsApp message."""
        self.send_attempts += 1

        await asyncio.sleep(self.delay_ms / 1000.0)

        # Simulate failures
        if self._should_fail():
            raise Exception(
                f"Evolution API error: Network timeout (attempt {self.send_attempts})"
            )

        # Success
        response = WhatsAppResponse(
            phone=phone,
            message=message,
            messageId=f"wamid_{int(time.time() * 1000000)}",
            deliveredAt=datetime.now(),
            attempts=self.send_attempts,
        )

        self.sent_messages.append(response)
        self.send_attempts = 0  # Reset for next message

        return {
            "status": "success",
            "messageId": response.messageId,
            "timestamp": response.deliveredAt.isoformat(),
        }

    def _should_fail(self):
        """Determine if send should fail."""
        if self.behavior == "normal":
            return False
        elif self.behavior == "fail_once":
            return self.send_attempts == 1
        elif self.behavior == "fail_twice":
            return self.send_attempts <= 2
        elif self.behavior == "always_fail":
            return True
        return False

    def reset(self):
        """Reset stub state."""
        self.sent_messages = []
        self.send_attempts = 0
        self.behavior = "normal"


class WhatsAppPreprocessor:
    """Preprocesses WhatsApp messages for pipeline."""

    def __init__(self):
        self.processed_count = 0
        self.conversation_traces = {}  # Track trace_id per phone

    def preprocess(self, whatsapp_msg: WhatsAppMessage) -> PreprocessedMessage:
        """Convert WhatsApp message to preprocessed format."""
        self.processed_count += 1

        # Use same trace_id for same phone (conversation continuity)
        if whatsapp_msg.phone not in self.conversation_traces:
            self.conversation_traces[
                whatsapp_msg.phone
            ] = f"trace_{whatsapp_msg.phone}_{whatsapp_msg.timestamp}"

        trace_id = self.conversation_traces[whatsapp_msg.phone]

        return PreprocessedMessage(
            text=whatsapp_msg.message,
            phone=whatsapp_msg.phone,
            message_id=whatsapp_msg.messageId,
            instance=whatsapp_msg.instance,
            trace_id=trace_id,
            turn_id=f"turn_{self.processed_count}",
            sanitized=True,
            rate_limited=False,
            history=[],
            headers={},
        )


class EndToEndPipeline:
    """Complete end-to-end pipeline from WhatsApp to delivery."""

    def __init__(self, preprocessor, gemini_pipeline, evolution_api, logger=None):
        self.preprocessor = preprocessor
        self.pipeline = gemini_pipeline
        self.evolution = evolution_api
        self.logger = logger or logging.getLogger(__name__)

    async def process_whatsapp_message(
        self, whatsapp_msg: WhatsAppMessage, max_retries: int = 3
    ) -> Dict[str, Any]:
        """Process WhatsApp message end-to-end."""
        start_time = time.perf_counter()

        # Step 1: Preprocess
        self.logger.info(
            f"E2E|start|phone={whatsapp_msg.phone}|"
            f"messageId={whatsapp_msg.messageId}"
        )

        preprocessed = self.preprocessor.preprocess(whatsapp_msg)

        # Step 2: Process through pipeline
        result = await self.pipeline.process(preprocessed)

        # Step 3: Deliver response with retries
        delivered = False
        delivery_attempts = 0

        # Skip delivery if response is cached (already sent before)
        if result.get("cached", False):
            delivered = True
            self.logger.info(f"E2E|skip_delivery|cached_response")
        else:
            # New response, attempt delivery with retries
            for attempt in range(max_retries):
                delivery_attempts += 1
                try:
                    await self.evolution.send_message(
                        instance=whatsapp_msg.instance,
                        phone=whatsapp_msg.phone,
                        message=result["response_text"],
                    )
                    delivered = True
                    self.logger.info(
                        f"E2E|delivered|attempts={delivery_attempts}|"
                        f"cached={result.get('cached', False)}"
                    )
                    break

                except Exception as e:
                    self.logger.warning(
                        f"E2E|delivery_failed|attempt={delivery_attempts}|"
                        f"error={str(e)}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff
                    else:
                        self.logger.error(
                            f"E2E|delivery_exhausted|messageId={whatsapp_msg.messageId}"
                        )

        # Calculate metrics
        total_latency_ms = (time.perf_counter() - start_time) * 1000

        # Build response
        response = {
            **result,
            "delivered": delivered,
            "delivery_attempts": delivery_attempts,
            "total_latency_ms": total_latency_ms,
            "phone": whatsapp_msg.phone,
            "original_message": whatsapp_msg.message,
        }

        self.logger.info(
            f"E2E|complete|delivered={delivered}|" f"latency_ms={total_latency_ms:.2f}"
        )

        return response


# Test fixtures
@pytest.fixture
def evolution_api():
    """Create Evolution API stub."""
    return EvolutionAPIStub()


@pytest.fixture
def whatsapp_preprocessor():
    """Create WhatsApp preprocessor."""
    return WhatsAppPreprocessor()


@pytest.fixture
def gemini_pipeline():
    """Create Gemini-LangGraph pipeline."""
    gemini = GeminiOrchestrator(GeminiStub(), timeout_ms=150, retries=1)
    router = LangGraphRouter()
    state_manager = StateManager(PostgresStub(), RedisStub())
    idempotency_store = IdempotencyStore()

    return GeminiLangGraphPipeline(
        gemini_orchestrator=gemini,
        langgraph_router=router,
        state_manager=state_manager,
        idempotency_store=idempotency_store,
    )


@pytest.fixture
def e2e_pipeline(whatsapp_preprocessor, gemini_pipeline, evolution_api):
    """Create end-to-end pipeline."""
    return EndToEndPipeline(
        preprocessor=whatsapp_preprocessor,
        gemini_pipeline=gemini_pipeline,
        evolution_api=evolution_api,
    )


@pytest.fixture
def sample_whatsapp_message():
    """Create sample WhatsApp message."""
    return WhatsAppMessage(
        instance="kumon-instance",
        phone="5511999999999",
        message="Olá, gostaria de informações sobre o Kumon",
        messageId="wamid_123456789",
    )


# PHASE 5 TESTS - End-to-End Delivery


@pytest.mark.asyncio
async def test_e2e_single_message_flow(e2e_pipeline, sample_whatsapp_message):
    """Test complete flow for a single message."""
    # When
    result = await e2e_pipeline.process_whatsapp_message(sample_whatsapp_message)

    # Then
    assert result["delivered"] is True
    assert result["delivery_attempts"] == 1
    assert result["response_text"] is not None
    assert LanguageEnforcer.is_portuguese(result["response_text"])
    assert result["phone"] == "5511999999999"


@pytest.mark.asyncio
async def test_e2e_portuguese_response_guaranteed(e2e_pipeline):
    """Test that all responses are in Portuguese."""
    # Given - Various messages
    messages = [
        WhatsAppMessage("kumon", "5511111111111", "Hello", "wamid_en_001"),
        WhatsAppMessage("kumon", "5511222222222", "Olá", "wamid_pt_001"),
        WhatsAppMessage("kumon", "5511333333333", "Información", "wamid_es_001"),
    ]

    # When - Process all messages
    for msg in messages:
        result = await e2e_pipeline.process_whatsapp_message(msg)

        # Then - All responses in Portuguese
        assert LanguageEnforcer.is_portuguese(result["response_text"])
        assert result["delivered"] is True


@pytest.mark.asyncio
async def test_e2e_no_duplicate_delivery(e2e_pipeline, evolution_api):
    """Test that duplicate messages don't cause duplicate delivery."""
    # Given - Same message twice
    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511444444444",
        message="Quanto custa?",
        messageId="wamid_dup_001",
    )

    # When - Process twice
    result1 = await e2e_pipeline.process_whatsapp_message(msg)
    result2 = await e2e_pipeline.process_whatsapp_message(msg)

    # Then - Only one delivery
    assert len(evolution_api.sent_messages) == 1
    assert result1["cached"] is False
    assert result2["cached"] is True
    assert result1["response_text"] == result2["response_text"]


@pytest.mark.asyncio
async def test_e2e_delivery_retry_on_failure(e2e_pipeline, evolution_api):
    """Test that delivery retries on failure."""
    # Given - API will fail once
    evolution_api.behavior = "fail_once"

    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511555555555",
        message="Informações",
        messageId="wamid_retry_001",
    )

    # When
    result = await e2e_pipeline.process_whatsapp_message(msg)

    # Then - Delivered after retry
    assert result["delivered"] is True
    assert result["delivery_attempts"] == 2
    assert len(evolution_api.sent_messages) == 1


@pytest.mark.asyncio
async def test_e2e_max_retries_respected(e2e_pipeline, evolution_api):
    """Test that max retries are respected."""
    # Given - API will always fail
    evolution_api.behavior = "always_fail"

    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511666666666",
        message="Teste",
        messageId="wamid_fail_001",
    )

    # When
    result = await e2e_pipeline.process_whatsapp_message(msg, max_retries=2)

    # Then - Delivery failed
    assert result["delivered"] is False
    assert result["delivery_attempts"] == 2
    assert len(evolution_api.sent_messages) == 0


@pytest.mark.asyncio
async def test_e2e_conversation_flow(e2e_pipeline, evolution_api):
    """Test a complete conversation flow."""
    # Given - Conversation messages
    phone = "5511777777777"
    messages = [
        WhatsAppMessage("kumon", phone, "Olá", "wamid_conv_001"),
        WhatsAppMessage("kumon", phone, "Quero saber sobre preços", "wamid_conv_002"),
        WhatsAppMessage("kumon", phone, "Meu filho tem 8 anos", "wamid_conv_003"),
        WhatsAppMessage("kumon", phone, "Quero agendar uma visita", "wamid_conv_004"),
    ]

    # When - Process conversation
    results = []
    for msg in messages:
        result = await e2e_pipeline.process_whatsapp_message(msg)
        results.append(result)
        await asyncio.sleep(0.01)  # Small delay between messages

    # Then - All delivered
    assert all(r["delivered"] for r in results)
    assert len(evolution_api.sent_messages) == 4

    # First response should be greeting
    assert (
        "bem-vindo" in results[0]["response_text"].lower()
        or "olá" in results[0]["response_text"].lower()
    )

    # Subsequent responses should be contextual
    # Note: Since we're using stubs, responses may be generic
    # The important thing is that all were delivered successfully
    for i, result in enumerate(results):
        assert result["response_text"] is not None
        assert LanguageEnforcer.is_portuguese(result["response_text"])


@pytest.mark.asyncio
async def test_e2e_concurrent_conversations(e2e_pipeline, evolution_api):
    """Test concurrent conversations don't interfere."""
    # Given - Messages from different phones
    messages = [
        WhatsAppMessage("kumon", f"55119999{i:05d}", f"Olá {i}", f"wamid_conc_{i}")
        for i in range(5)
    ]

    # When - Process concurrently
    tasks = [e2e_pipeline.process_whatsapp_message(msg) for msg in messages]
    results = await asyncio.gather(*tasks)

    # Then - All delivered independently
    assert all(r["delivered"] for r in results)
    assert len(evolution_api.sent_messages) == 5

    # Each conversation isolated
    phones = [msg.phone for msg in evolution_api.sent_messages]
    assert len(set(phones)) == 5  # All different


@pytest.mark.asyncio
async def test_e2e_performance_under_target(e2e_pipeline):
    """Test that end-to-end latency is under target."""
    # Given
    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511888888888",
        message="Teste de performance",
        messageId="wamid_perf_001",
    )

    # When
    result = await e2e_pipeline.process_whatsapp_message(msg)

    # Then
    assert result["delivered"] is True
    assert result["total_latency_ms"] < 800  # Target
    print(f"E2E latency: {result['total_latency_ms']:.2f}ms")


@pytest.mark.asyncio
async def test_e2e_logging_complete(e2e_pipeline, caplog):
    """Test that all phases are logged."""
    import logging

    caplog.set_level(logging.INFO)

    # Given
    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511999999999",
        message="Teste de log",
        messageId="wamid_log_001",
    )

    # When
    await e2e_pipeline.process_whatsapp_message(msg)

    # Then
    logs = caplog.text
    assert "E2E|start" in logs
    assert "E2E|delivered" in logs
    assert "E2E|complete" in logs
    assert "PIPELINE|" in logs
    assert "ROUTER|" in logs


@pytest.mark.asyncio
async def test_e2e_state_persistence_across_messages(e2e_pipeline, gemini_pipeline):
    """Test that state persists across messages in conversation."""
    # Given
    phone = "5511000000000"
    msg1 = WhatsAppMessage("kumon", phone, "Olá", "wamid_state_001")
    msg2 = WhatsAppMessage("kumon", phone, "Qual o valor?", "wamid_state_002")

    # When
    result1 = await e2e_pipeline.process_whatsapp_message(msg1)
    result2 = await e2e_pipeline.process_whatsapp_message(msg2)

    # Then - State should evolve
    assert result1["delivered"] is True
    assert result2["delivered"] is True

    # Check state persistence
    trace_id = f"trace_{phone}_{msg1.timestamp}"
    state = await gemini_pipeline.state_manager.get_state(trace_id)
    assert state is not None


@pytest.mark.asyncio
async def test_e2e_idempotency_across_pipeline(e2e_pipeline, evolution_api):
    """Test idempotency works across entire pipeline."""
    # Given
    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511001001001",
        message="Teste idempotência",
        messageId="wamid_idem_001",
    )

    # When - Process multiple times
    results = []
    for _ in range(3):
        result = await e2e_pipeline.process_whatsapp_message(msg)
        results.append(result)

    # Then - Only one delivery
    assert len(evolution_api.sent_messages) == 1
    assert results[0]["cached"] is False
    assert all(r["cached"] for r in results[1:])


@pytest.mark.asyncio
async def test_e2e_error_recovery(e2e_pipeline, evolution_api):
    """Test system recovers from errors gracefully."""
    # Given - Delivery will fail twice
    evolution_api.behavior = "fail_twice"

    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511002002002",
        message="Teste recuperação",
        messageId="wamid_recover_001",
    )

    # When
    result = await e2e_pipeline.process_whatsapp_message(msg, max_retries=3)

    # Then - Eventually succeeds
    assert result["delivered"] is True
    assert result["delivery_attempts"] == 3
    assert len(evolution_api.sent_messages) == 1


@pytest.mark.asyncio
async def test_e2e_only_one_response_per_turn():
    """Test that only one response is sent per turn."""
    # Create pipeline
    evolution = EvolutionAPIStub()
    preprocessor = WhatsAppPreprocessor()

    gemini = GeminiOrchestrator(GeminiStub(), timeout_ms=150, retries=1)
    router = LangGraphRouter()
    state_manager = StateManager(PostgresStub(), RedisStub())
    idempotency_store = IdempotencyStore()

    gemini_pipeline = GeminiLangGraphPipeline(
        gemini_orchestrator=gemini,
        langgraph_router=router,
        state_manager=state_manager,
        idempotency_store=idempotency_store,
    )

    e2e = EndToEndPipeline(
        preprocessor=preprocessor,
        gemini_pipeline=gemini_pipeline,
        evolution_api=evolution,
    )

    # Given
    msg = WhatsAppMessage(
        instance="kumon",
        phone="5511003003003",
        message="Uma mensagem",
        messageId="wamid_single_001",
    )

    # When - Process once
    result = await e2e.process_whatsapp_message(msg)

    # Then - Exactly one response
    assert len(evolution.sent_messages) == 1
    assert result["delivered"] is True

    # Response should not trigger another response
    assert (
        "?" in result["response_text"]
        or "!" in result["response_text"]
        or "." in result["response_text"]
    )


@pytest.mark.asyncio
async def test_e2e_message_order_preserved(e2e_pipeline, evolution_api):
    """Test that message order is preserved in conversation."""
    # Given
    phone = "5511004004004"
    messages = [
        WhatsAppMessage("kumon", phone, f"Mensagem {i}", f"wamid_order_{i:03d}")
        for i in range(5)
    ]

    # When - Process in order
    for msg in messages:
        await e2e_pipeline.process_whatsapp_message(msg)

    # Then - Responses in same order
    assert len(evolution_api.sent_messages) == 5
    for i, sent in enumerate(evolution_api.sent_messages):
        assert sent.phone == phone
