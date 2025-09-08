"""
Phase 3 - Idempotency Tests
Tests idempotency system to prevent duplicate message processing.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import pytest


@dataclass
class Message:
    """Incoming message."""

    message_id: str
    conversation_id: str
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessedMessage:
    """Record of processed message."""

    idempotency_key: str
    message_id: str
    conversation_id: str
    response_text: str
    stage_before: str
    stage_after: str
    processed_at: datetime
    retry_count: int = 0


class IdempotencyStore:
    """Store for idempotency keys."""

    def __init__(self, postgres_client=None):
        self.postgres = postgres_client
        self.processed = {}  # In-memory for testing
        self._lock = asyncio.Lock()  # For concurrent access

    async def has_been_processed(self, idempotency_key: str) -> bool:
        """Check if message was already processed."""
        async with self._lock:
            if self.postgres:
                result = await self.postgres.get_idempotency(idempotency_key)
                return result is not None
            return idempotency_key in self.processed

    async def mark_processed(
        self,
        idempotency_key: str,
        message_id: str,
        conversation_id: str,
        response_text: str,
        stage_before: str,
        stage_after: str,
    ) -> bool:
        """Mark message as processed."""
        async with self._lock:
            # Check again inside lock (double-check pattern)
            if idempotency_key in self.processed:
                return False  # Already processed

            record = ProcessedMessage(
                idempotency_key=idempotency_key,
                message_id=message_id,
                conversation_id=conversation_id,
                response_text=response_text,
                stage_before=stage_before,
                stage_after=stage_after,
                processed_at=datetime.now(),
            )

            if self.postgres:
                return await self.postgres.save_idempotency(idempotency_key, record)

            self.processed[idempotency_key] = record
            return True

    async def get_processed_response(
        self, idempotency_key: str
    ) -> Optional[ProcessedMessage]:
        """Get previously processed response."""
        if self.postgres:
            return await self.postgres.get_idempotency(idempotency_key)
        return self.processed.get(idempotency_key)

    def reset(self):
        """Reset store for testing."""
        self.processed = {}


class IdempotentProcessor:
    """Processor with idempotency guarantees."""

    def __init__(self, idempotency_store, state_manager, node_executor, logger=None):
        self.idempotency_store = idempotency_store
        self.state_manager = state_manager
        self.node_executor = node_executor
        self.logger = logger or logging.getLogger(__name__)

    def _generate_idempotency_key(self, conversation_id: str, message_id: str) -> str:
        """Generate idempotency key."""
        return f"{conversation_id}:{message_id}"

    async def process_message(self, message: Message) -> Dict[str, Any]:
        """Process message with idempotency check."""
        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(
            message.conversation_id, message.message_id
        )

        # Check if already processed
        if await self.idempotency_store.has_been_processed(idempotency_key):
            # Return cached response
            self.logger.info(f"IDEMPOTENT|skip|key={idempotency_key}")
            cached = await self.idempotency_store.get_processed_response(
                idempotency_key
            )
            return {
                "response_text": cached.response_text,
                "cached": True,
                "stage": cached.stage_after,
                "idempotency_key": idempotency_key,
            }

        # Process new message
        self.logger.info(f"IDEMPOTENT|process|key={idempotency_key}")

        # Get current state
        state = await self.state_manager.get_state(message.conversation_id)
        if not state:
            # Initialize new conversation
            from tests.langgraph.test_phase2_state_persistence import ConversationState

            state = ConversationState(
                conversation_id=message.conversation_id,
                session_id=f"sess_{message.conversation_id}",
                phone_number="unknown",
                stage="greeting",
            )
            await self.state_manager.save_state(state)

        stage_before = state.stage

        # Execute node based on current stage
        response = await self.node_executor.execute(state, message.text)

        # Update state if stage changed
        if response.stage_update != state.stage:
            await self.state_manager.update_stage(
                message.conversation_id, response.stage_update
            )

        # Mark as processed (atomically with double-check)
        success = await self.idempotency_store.mark_processed(
            idempotency_key=idempotency_key,
            message_id=message.message_id,
            conversation_id=message.conversation_id,
            response_text=response.response_text,
            stage_before=stage_before,
            stage_after=response.stage_update,
        )

        if not success:
            # Someone else processed it while we were working
            self.logger.info(f"IDEMPOTENT|race_condition|key={idempotency_key}")
            cached = await self.idempotency_store.get_processed_response(
                idempotency_key
            )
            return {
                "response_text": cached.response_text,
                "cached": True,
                "stage": cached.stage_after,
                "idempotency_key": idempotency_key,
            }

        return {
            "response_text": response.response_text,
            "cached": False,
            "stage": response.stage_update,
            "idempotency_key": idempotency_key,
        }


class DeliverySimulator:
    """Simulates message delivery with retries."""

    def __init__(self, processor, logger=None):
        self.processor = processor
        self.logger = logger or logging.getLogger(__name__)
        self.delivered = []
        self.delivery_attempts = 0
        self.behavior = "normal"  # normal, fail_once, fail_twice, always_fail

    async def deliver(self, message: Message, max_retries: int = 3) -> bool:
        """Deliver message with retries."""
        for attempt in range(max_retries):
            self.delivery_attempts += 1

            try:
                # Process message (may be cached)
                result = await self.processor.process_message(message)

                # Simulate delivery
                if self._should_fail(attempt):
                    self.logger.info(f"DELIVERY|fail|attempt={attempt + 1}")
                    raise Exception("Delivery failed")

                # Success
                self.logger.info(
                    f"DELIVERY|success|attempt={attempt + 1}|cached={result['cached']}"
                )
                self.delivered.append(
                    {
                        "message_id": message.message_id,
                        "response": result["response_text"],
                        "attempts": attempt + 1,
                        "cached": result["cached"],
                    }
                )
                return True

            except Exception:
                if attempt == max_retries - 1:
                    self.logger.error(
                        f"DELIVERY|exhausted|message_id={message.message_id}"
                    )
                    return False
                await asyncio.sleep(0.01 * (2**attempt))  # Exponential backoff

        return False

    def _should_fail(self, attempt: int) -> bool:
        """Determine if delivery should fail."""
        if self.behavior == "normal":
            return False
        elif self.behavior == "fail_once":
            return attempt == 0
        elif self.behavior == "fail_twice":
            return attempt < 2
        elif self.behavior == "always_fail":
            return True
        return False

    def reset(self):
        """Reset delivery history."""
        self.delivered = []
        self.delivery_attempts = 0
        self.behavior = "normal"


# Test fixtures
@pytest.fixture
def idempotency_store():
    """Create idempotency store."""
    return IdempotencyStore()


@pytest.fixture
def state_manager():
    """Create state manager stub."""
    from tests.langgraph.test_phase2_state_persistence import (
        PostgresStub,
        RedisStub,
        StateManager,
    )

    return StateManager(PostgresStub(), RedisStub())


@pytest.fixture
def node_executor():
    """Create node executor stub."""
    from tests.langgraph.test_phase1_node_execution import GreetingNode

    return GreetingNode()


@pytest.fixture
def logger():
    """Create test logger."""
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    return logger


@pytest.fixture
def processor(idempotency_store, state_manager, node_executor, logger):
    """Create idempotent processor."""
    return IdempotentProcessor(idempotency_store, state_manager, node_executor, logger)


@pytest.fixture
def delivery_simulator(processor, logger):
    """Create delivery simulator."""
    return DeliverySimulator(processor, logger)


# PHASE 3 TESTS - Idempotency


@pytest.mark.asyncio
async def test_idempotency_key_generation(processor):
    """Test that idempotency keys are correctly generated."""
    # When
    key = processor._generate_idempotency_key("conv_123", "msg_456")

    # Then
    assert key == "conv_123:msg_456"


@pytest.mark.asyncio
async def test_first_message_processing(processor):
    """Test that first message is processed normally."""
    # Given
    message = Message(message_id="msg_001", conversation_id="conv_001", text="Olá")

    # When
    result = await processor.process_message(message)

    # Then
    assert result["cached"] is False
    assert result["response_text"] is not None
    assert result["stage"] == "qualification"  # Greeting -> Qualification
    assert result["idempotency_key"] == "conv_001:msg_001"


@pytest.mark.asyncio
async def test_duplicate_message_returns_cached(processor):
    """Test that duplicate message returns cached response."""
    # Given
    message = Message(message_id="msg_dup", conversation_id="conv_dup", text="Olá")

    # When - Process first time
    result1 = await processor.process_message(message)
    assert result1["cached"] is False

    # When - Process same message again
    result2 = await processor.process_message(message)

    # Then - Should return cached
    assert result2["cached"] is True
    assert result2["response_text"] == result1["response_text"]
    assert result2["stage"] == result1["stage"]


@pytest.mark.asyncio
async def test_idempotency_store_persistence(idempotency_store):
    """Test that idempotency store persists records."""
    # When - Mark as processed
    await idempotency_store.mark_processed(
        idempotency_key="conv_test:msg_test",
        message_id="msg_test",
        conversation_id="conv_test",
        response_text="Test response",
        stage_before="greeting",
        stage_after="qualification",
    )

    # Then - Can check if processed
    assert await idempotency_store.has_been_processed("conv_test:msg_test")

    # And - Can retrieve response
    cached = await idempotency_store.get_processed_response("conv_test:msg_test")
    assert cached is not None
    assert cached.response_text == "Test response"
    assert cached.stage_before == "greeting"
    assert cached.stage_after == "qualification"


@pytest.mark.asyncio
async def test_no_duplicate_state_changes(processor, state_manager):
    """Test that duplicate messages don't change state."""
    # Given
    message = Message(message_id="msg_state", conversation_id="conv_state", text="Olá")

    # When - Process first time
    await processor.process_message(message)
    state1 = await state_manager.get_state("conv_state")

    # When - Process duplicate
    await processor.process_message(message)
    state2 = await state_manager.get_state("conv_state")

    # Then - State unchanged
    assert state1.stage == state2.stage
    assert state1.updated_at == state2.updated_at


@pytest.mark.asyncio
async def test_delivery_retry_with_idempotency(delivery_simulator):
    """Test that delivery retry doesn't duplicate responses."""
    # Given - Delivery will fail once
    delivery_simulator.behavior = "fail_once"

    message = Message(message_id="msg_retry", conversation_id="conv_retry", text="Olá")

    # When - Deliver with retry
    success = await delivery_simulator.deliver(message)

    # Then
    assert success
    assert len(delivery_simulator.delivered) == 1  # Only one delivery
    assert delivery_simulator.delivered[0]["attempts"] == 2  # Took 2 attempts
    assert delivery_simulator.delivery_attempts == 2


@pytest.mark.asyncio
async def test_multiple_retries_same_response(delivery_simulator):
    """Test that multiple retries return the same response."""
    # Given - Delivery will fail twice
    delivery_simulator.behavior = "fail_twice"

    message = Message(
        message_id="msg_multi_retry", conversation_id="conv_multi_retry", text="Olá"
    )

    # When - Deliver with retries
    success = await delivery_simulator.deliver(message)

    # Then
    assert success
    assert len(delivery_simulator.delivered) == 1
    assert delivery_simulator.delivered[0]["attempts"] == 3
    # Second and third attempts should use cached response


@pytest.mark.asyncio
async def test_concurrent_duplicate_requests(processor):
    """Test that concurrent duplicate requests are handled correctly."""
    # Given
    message = Message(
        message_id="msg_concurrent", conversation_id="conv_concurrent", text="Olá"
    )

    # When - Process same message concurrently
    tasks = [processor.process_message(message) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # Then - First processed, rest cached
    cached_count = sum(1 for r in results if r["cached"])
    assert cached_count >= 4  # At least 4 should be cached

    # All should have same response
    response_texts = [r["response_text"] for r in results]
    assert len(set(response_texts)) == 1  # All same


@pytest.mark.asyncio
async def test_different_messages_same_conversation(processor):
    """Test that different messages in same conversation are processed."""
    # Given
    messages = [
        Message("msg_001", "conv_seq", "Olá"),
        Message("msg_002", "conv_seq", "Quero informações"),
        Message("msg_003", "conv_seq", "Sobre preços"),
    ]

    # When - Process each message
    results = []
    for msg in messages:
        result = await processor.process_message(msg)
        results.append(result)

    # Then - All processed (not cached)
    assert all(not r["cached"] for r in results)

    # And - Different idempotency keys
    keys = [r["idempotency_key"] for r in results]
    assert len(set(keys)) == 3


@pytest.mark.asyncio
async def test_idempotency_logging(processor, caplog):
    """Test that idempotency events are logged."""
    import logging

    caplog.set_level(logging.INFO)

    # Given
    message = Message(message_id="msg_log", conversation_id="conv_log", text="Test")

    # When - Process twice
    await processor.process_message(message)
    await processor.process_message(message)

    # Then - Check logs
    logs = caplog.text
    assert "IDEMPOTENT|process|key=conv_log:msg_log" in logs
    assert "IDEMPOTENT|skip|key=conv_log:msg_log" in logs


@pytest.mark.asyncio
async def test_delivery_logging(delivery_simulator, caplog):
    """Test that delivery events are logged."""
    import logging

    caplog.set_level(logging.INFO)

    # Given
    delivery_simulator.behavior = "fail_once"
    message = Message("msg_del_log", "conv_del_log", "Test")

    # When
    await delivery_simulator.deliver(message)

    # Then
    logs = caplog.text
    assert "DELIVERY|fail|attempt=1" in logs
    assert "DELIVERY|success|attempt=2" in logs


@pytest.mark.asyncio
async def test_exhausted_retries_logging(delivery_simulator, caplog):
    """Test that exhausted retries are logged."""
    import logging

    caplog.set_level(logging.INFO)

    # Given
    delivery_simulator.behavior = "always_fail"
    message = Message("msg_exhaust", "conv_exhaust", "Test")

    # When
    success = await delivery_simulator.deliver(message, max_retries=2)

    # Then
    assert not success
    logs = caplog.text
    assert "DELIVERY|exhausted|message_id=msg_exhaust" in logs


@pytest.mark.asyncio
async def test_idempotency_across_sessions(processor, idempotency_store):
    """Test that idempotency works across different sessions."""
    # Given - Process in "session 1"
    message = Message("msg_session", "conv_session", "Olá")
    result1 = await processor.process_message(message)

    # When - Simulate new session (same store)
    # In real scenario, this would be a new request/connection
    result2 = await processor.process_message(message)

    # Then - Still returns cached
    assert result2["cached"] is True
    assert result2["response_text"] == result1["response_text"]


@pytest.mark.asyncio
async def test_idempotency_key_collision_prevention():
    """Test that idempotency keys don't collide."""
    # Different conversations with same message_id
    key1 = IdempotentProcessor._generate_idempotency_key(None, "conv_A", "msg_123")
    key2 = IdempotentProcessor._generate_idempotency_key(None, "conv_B", "msg_123")
    assert key1 != key2

    # Same conversation with different message_ids
    key3 = IdempotentProcessor._generate_idempotency_key(None, "conv_A", "msg_123")
    key4 = IdempotentProcessor._generate_idempotency_key(None, "conv_A", "msg_456")
    assert key3 != key4
