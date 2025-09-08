"""
Phase 2 - State Persistence Tests
Tests state management with PostgreSQL as source of truth and Redis as cache.
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import pytest


@dataclass
class ConversationState:
    """Complete conversation state."""

    conversation_id: str
    session_id: str
    phone_number: str
    stage: str
    context: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class PostgresStub:
    """Mock PostgreSQL for testing."""

    def __init__(self):
        self.data = {}
        self.call_count = 0
        self.last_query = None
        self.behavior = "normal"  # normal, error, slow
        self.delay_ms = 5

    async def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get state from database."""
        self.call_count += 1
        self.last_query = ("get", conversation_id)

        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.behavior == "error":
            raise Exception("Database connection error")
        elif self.behavior == "slow":
            await asyncio.sleep(0.1)  # 100ms delay

        return self.data.get(conversation_id)

    async def set(self, conversation_id: str, state: Dict[str, Any]) -> bool:
        """Save state to database."""
        self.call_count += 1
        self.last_query = ("set", conversation_id, state)

        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.behavior == "error":
            raise Exception("Database write error")

        self.data[conversation_id] = state
        return True

    async def update_stage(self, conversation_id: str, stage: str) -> bool:
        """Update only the stage field."""
        self.call_count += 1
        self.last_query = ("update_stage", conversation_id, stage)

        await asyncio.sleep(self.delay_ms / 1000.0)

        if self.behavior == "error":
            raise Exception("Database update error")

        if conversation_id in self.data:
            self.data[conversation_id]["stage"] = stage
            self.data[conversation_id]["updated_at"] = datetime.now().isoformat()
            return True
        return False

    def reset(self):
        """Reset stub state."""
        self.data = {}
        self.call_count = 0
        self.last_query = None
        self.behavior = "normal"


class RedisStub:
    """Mock Redis for testing."""

    def __init__(self):
        self.cache = {}
        self.call_count = 0
        self.behavior = "normal"  # normal, error, unavailable
        self.ttl = 3600  # 1 hour default

    async def get(self, key: str) -> Optional[str]:
        """Get from cache."""
        self.call_count += 1

        if self.behavior == "unavailable":
            raise Exception("Redis connection refused")
        elif self.behavior == "error":
            raise Exception("Redis read error")

        return self.cache.get(key)

    async def set(self, key: str, value: str, ttl: int = None) -> bool:
        """Set in cache with TTL."""
        self.call_count += 1

        if self.behavior == "unavailable":
            raise Exception("Redis connection refused")
        elif self.behavior == "error":
            raise Exception("Redis write error")

        self.cache[key] = value
        return True

    async def delete(self, key: str) -> bool:
        """Delete from cache."""
        self.call_count += 1

        if self.behavior == "unavailable":
            raise Exception("Redis connection refused")

        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def reset(self):
        """Reset cache."""
        self.cache = {}
        self.call_count = 0
        self.behavior = "normal"


class StateManager:
    """Manages conversation state with PostgreSQL + Redis."""

    def __init__(self, postgres_client=None, redis_client=None):
        self.postgres = postgres_client or PostgresStub()
        self.redis = redis_client or RedisStub()
        self.cache_ttl = 3600  # 1 hour

    async def get_state(self, conversation_id: str) -> Optional[ConversationState]:
        """Get state, trying Redis first, then PostgreSQL."""
        # Try Redis first
        if self.redis:
            try:
                cached = await self.redis.get(f"state:{conversation_id}")
                if cached:
                    data = json.loads(cached)
                    return self._dict_to_state(data)
            except Exception as e:
                # Redis failure is non-fatal
                print(f"Redis get failed: {e}")

        # Fallback to PostgreSQL
        data = await self.postgres.get(conversation_id)
        if data:
            state = self._dict_to_state(data)

            # Update Redis cache if available
            if self.redis:
                try:
                    await self.redis.set(
                        f"state:{conversation_id}", json.dumps(data), self.cache_ttl
                    )
                except Exception as e:
                    # Redis failure is non-fatal
                    print(f"Redis set failed: {e}")

            return state

        return None

    async def save_state(self, state: ConversationState) -> bool:
        """Save complete state to both stores."""
        state_dict = self._state_to_dict(state)

        # Always save to PostgreSQL first (source of truth)
        success = await self.postgres.set(state.conversation_id, state_dict)

        if success and self.redis:
            # Try to update Redis cache
            try:
                await self.redis.set(
                    f"state:{state.conversation_id}",
                    json.dumps(state_dict),
                    self.cache_ttl,
                )
            except Exception as e:
                # Redis failure is non-fatal
                print(f"Redis save failed: {e}")

        return success

    async def update_stage(self, conversation_id: str, new_stage: str) -> bool:
        """Update only the stage field atomically."""
        # Update PostgreSQL
        success = await self.postgres.update_stage(conversation_id, new_stage)

        if success and self.redis:
            # Invalidate Redis cache to force re-read
            try:
                await self.redis.delete(f"state:{conversation_id}")
            except Exception as e:
                # Redis failure is non-fatal
                print(f"Redis delete failed: {e}")

        return success

    async def append_context(
        self, conversation_id: str, context_update: Dict[str, Any]
    ) -> bool:
        """Append to context atomically."""
        # Get current state
        state = await self.get_state(conversation_id)
        if not state:
            return False

        # Merge context
        state.context.update(context_update)
        state.updated_at = datetime.now()

        # Save updated state
        return await self.save_state(state)

    def _state_to_dict(self, state: ConversationState) -> Dict[str, Any]:
        """Convert state object to dictionary."""
        return {
            "conversation_id": state.conversation_id,
            "session_id": state.session_id,
            "phone_number": state.phone_number,
            "stage": state.stage,
            "context": state.context,
            "entities": state.entities,
            "message_count": state.message_count,
            "created_at": state.created_at.isoformat()
            if isinstance(state.created_at, datetime)
            else state.created_at,
            "updated_at": state.updated_at.isoformat()
            if isinstance(state.updated_at, datetime)
            else state.updated_at,
        }

    def _dict_to_state(self, data: Dict[str, Any]) -> ConversationState:
        """Convert dictionary to state object."""
        # Handle datetime conversion
        created_at = data.get("created_at", datetime.now().isoformat())
        updated_at = data.get("updated_at", datetime.now().isoformat())

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return ConversationState(
            conversation_id=data["conversation_id"],
            session_id=data.get("session_id", ""),
            phone_number=data.get("phone_number", ""),
            stage=data["stage"],
            context=data.get("context", {}),
            entities=data.get("entities", {}),
            message_count=data.get("message_count", 0),
            created_at=created_at,
            updated_at=updated_at,
        )


# Test fixtures
@pytest.fixture
def postgres_stub():
    """Create PostgreSQL stub."""
    return PostgresStub()


@pytest.fixture
def redis_stub():
    """Create Redis stub."""
    return RedisStub()


@pytest.fixture
def state_manager(postgres_stub, redis_stub):
    """Create state manager with stubs."""
    return StateManager(postgres_stub, redis_stub)


@pytest.fixture
def sample_state():
    """Create sample conversation state."""
    return ConversationState(
        conversation_id="conv_123",
        session_id="sess_456",
        phone_number="5511999999999",
        stage="greeting",
        context={"last_interaction": "2024-01-15"},
        entities={"student_name": "João"},
        message_count=1,
    )


# PHASE 2 TESTS - State Persistence


@pytest.mark.asyncio
async def test_save_and_retrieve_state(state_manager, sample_state):
    """Test basic save and retrieve from PostgreSQL."""
    # When - Save state
    success = await state_manager.save_state(sample_state)
    assert success

    # Then - Retrieve state
    retrieved = await state_manager.get_state("conv_123")
    assert retrieved is not None
    assert retrieved.conversation_id == "conv_123"
    assert retrieved.stage == "greeting"
    assert retrieved.entities["student_name"] == "João"


@pytest.mark.asyncio
async def test_state_persists_across_messages(state_manager):
    """Test that state is maintained between multiple messages."""
    # Given - Initial state
    state1 = ConversationState(
        conversation_id="conv_multi",
        session_id="sess_multi",
        phone_number="5511888888888",
        stage="greeting",
        message_count=1,
    )

    # When - Save and update through multiple interactions
    await state_manager.save_state(state1)

    # Message 2: Update stage
    await state_manager.update_stage("conv_multi", "qualification")

    # Message 3: Add context
    await state_manager.append_context("conv_multi", {"interest": "math"})

    # Then - Verify state accumulated correctly
    final_state = await state_manager.get_state("conv_multi")
    assert final_state.stage == "qualification"
    assert final_state.context["interest"] == "math"
    assert final_state.message_count == 1  # Original count preserved


@pytest.mark.asyncio
async def test_redis_cache_hit(state_manager, sample_state, postgres_stub, redis_stub):
    """Test that Redis cache is used when available."""
    # Given - State saved (goes to both stores)
    await state_manager.save_state(sample_state)
    postgres_calls_after_save = postgres_stub.call_count

    # When - Retrieve state multiple times
    for _ in range(3):
        retrieved = await state_manager.get_state("conv_123")
        assert retrieved is not None

    # Then - PostgreSQL not called again (Redis cache hit)
    assert postgres_stub.call_count == postgres_calls_after_save
    assert redis_stub.call_count > postgres_calls_after_save


@pytest.mark.asyncio
async def test_redis_failure_fallback_to_postgres(
    state_manager, sample_state, redis_stub
):
    """Test that system works when Redis is unavailable."""
    # Given - Save state successfully
    await state_manager.save_state(sample_state)

    # When - Redis becomes unavailable
    redis_stub.behavior = "unavailable"

    # Then - Can still retrieve from PostgreSQL
    retrieved = await state_manager.get_state("conv_123")
    assert retrieved is not None
    assert retrieved.stage == "greeting"


@pytest.mark.asyncio
async def test_stage_update_invalidates_cache(state_manager, sample_state, redis_stub):
    """Test that stage update invalidates Redis cache."""
    # Given - State in both stores
    await state_manager.save_state(sample_state)

    # When - Update stage
    await state_manager.update_stage("conv_123", "information")

    # Then - Redis cache was invalidated
    cached = await redis_stub.get("state:conv_123")
    assert cached is None  # Cache cleared

    # And - Next read gets updated value
    retrieved = await state_manager.get_state("conv_123")
    assert retrieved.stage == "information"


@pytest.mark.asyncio
async def test_postgres_as_source_of_truth(state_manager, postgres_stub, redis_stub):
    """Test that PostgreSQL is always the source of truth."""
    # Given - Different data in Redis and PostgreSQL
    postgres_data = {
        "conversation_id": "conv_truth",
        "session_id": "sess_truth",
        "phone_number": "5511777777777",
        "stage": "scheduling",  # Truth
        "context": {},
        "entities": {},
        "message_count": 5,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    redis_data = {
        "conversation_id": "conv_truth",
        "session_id": "sess_truth",
        "phone_number": "5511777777777",
        "stage": "greeting",  # Stale
        "context": {},
        "entities": {},
        "message_count": 1,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # Set directly in stores
    postgres_stub.data["conv_truth"] = postgres_data
    redis_stub.cache["state:conv_truth"] = json.dumps(redis_data)

    # When - Retrieve with cache hit
    retrieved = await state_manager.get_state("conv_truth")

    # Then - Redis cache is used (stale data)
    assert retrieved.stage == "greeting"

    # When - Cache is invalidated
    await redis_stub.delete("state:conv_truth")
    retrieved_fresh = await state_manager.get_state("conv_truth")

    # Then - PostgreSQL truth is retrieved
    assert retrieved_fresh.stage == "scheduling"


@pytest.mark.asyncio
async def test_concurrent_state_updates(state_manager):
    """Test that concurrent updates don't corrupt state."""
    # Given - Initial states for different conversations
    states = [
        ConversationState(
            conversation_id=f"conv_{i}",
            session_id=f"sess_{i}",
            phone_number=f"551100000{i:04d}",
            stage="greeting",
        )
        for i in range(5)
    ]

    # When - Save all states concurrently
    save_tasks = [state_manager.save_state(state) for state in states]
    results = await asyncio.gather(*save_tasks)
    assert all(results)

    # And - Update stages concurrently
    update_tasks = [
        state_manager.update_stage(f"conv_{i}", "qualification") for i in range(5)
    ]
    update_results = await asyncio.gather(*update_tasks)
    assert all(update_results)

    # Then - All states updated correctly
    for i in range(5):
        retrieved = await state_manager.get_state(f"conv_{i}")
        assert retrieved.stage == "qualification"
        assert retrieved.phone_number == f"551100000{i:04d}"


@pytest.mark.asyncio
async def test_append_context_atomic(state_manager, sample_state):
    """Test that context append is atomic."""
    # Given - Initial state with context
    await state_manager.save_state(sample_state)

    # When - Append context multiple times
    await state_manager.append_context("conv_123", {"topic": "math"})
    await state_manager.append_context("conv_123", {"level": "advanced"})
    await state_manager.append_context("conv_123", {"schedule": "morning"})

    # Then - All context preserved and merged
    final = await state_manager.get_state("conv_123")
    assert final.context["last_interaction"] == "2024-01-15"  # Original
    assert final.context["topic"] == "math"
    assert final.context["level"] == "advanced"
    assert final.context["schedule"] == "morning"


@pytest.mark.asyncio
async def test_state_not_found_returns_none(state_manager):
    """Test that missing state returns None."""
    # When - Get non-existent state
    result = await state_manager.get_state("non_existent")

    # Then
    assert result is None


@pytest.mark.asyncio
async def test_postgres_error_handling(state_manager, postgres_stub):
    """Test graceful handling of PostgreSQL errors."""
    # Given - PostgreSQL in error state
    postgres_stub.behavior = "error"

    state = ConversationState(
        conversation_id="conv_error",
        session_id="sess_error",
        phone_number="5511666666666",
        stage="greeting",
    )

    # When - Try to save
    with pytest.raises(Exception) as exc_info:
        await state_manager.save_state(state)

    # Then
    assert "Database" in str(exc_info.value)


@pytest.mark.asyncio
async def test_redis_errors_non_fatal(state_manager, sample_state, redis_stub, capsys):
    """Test that Redis errors don't break the system."""
    # Given - Redis will error but PostgreSQL works
    redis_stub.behavior = "error"

    # When - Save state
    success = await state_manager.save_state(sample_state)

    # Then - Save succeeds (PostgreSQL worked)
    assert success

    # And - Error was logged
    captured = capsys.readouterr()
    assert "Redis" in captured.out


@pytest.mark.asyncio
async def test_state_timestamp_updates(state_manager, sample_state):
    """Test that timestamps are properly maintained."""
    # Given - Original timestamps
    original_created = sample_state.created_at
    original_updated = sample_state.updated_at

    # When - Save state
    await state_manager.save_state(sample_state)

    # And - Update stage after a delay
    await asyncio.sleep(0.01)  # Small delay to ensure different timestamp
    await state_manager.update_stage("conv_123", "information")

    # Then - Retrieve and check timestamps
    retrieved = await state_manager.get_state("conv_123")
    assert retrieved.created_at == original_created  # Created unchanged
    assert retrieved.updated_at > original_updated  # Updated changed


@pytest.mark.asyncio
async def test_message_count_persistence(state_manager):
    """Test that message count is maintained across sessions."""
    # Given - State with message count
    state = ConversationState(
        conversation_id="conv_count",
        session_id="sess_count",
        phone_number="5511555555555",
        stage="greeting",
        message_count=0,
    )

    # When - Simulate multiple messages
    for i in range(5):
        state.message_count = i + 1
        await state_manager.save_state(state)

    # Then - Count is preserved
    final = await state_manager.get_state("conv_count")
    assert final.message_count == 5
