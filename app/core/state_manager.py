"""
Conversation state management module.
Handles Redis-backed state persistence with fallback for testing.
"""
import json
import os
from typing import Any, Dict

try:
    import redis

    redis_client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
    )
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# In-memory fallback for testing
_memory_store: Dict[str, str] = {}


def get_conversation_state(phone: str) -> Dict[str, Any]:
    """Retrieve conversation state for a phone number."""
    if not phone:
        return {}

    # Remove + prefix and use as session key
    session_key = f"conversation:{phone.lstrip('+')}"

    try:
        if REDIS_AVAILABLE:
            state_json = redis_client.get(session_key)
            if state_json:
                return json.loads(state_json)
        else:
            # Fallback to memory store
            state_json = _memory_store.get(session_key)
            if state_json:
                return json.loads(state_json)
    except Exception as e:
        print(f"STATE|error_loading|key={session_key}|error={str(e)}")

    return {}


def save_conversation_state(phone: str, state: Dict[str, Any]) -> bool:
    """Save conversation state with 30 minute TTL."""
    if not phone or not state:
        return False

    # Remove + prefix and use as session key
    session_key = f"conversation:{phone.lstrip('+')}"

    try:
        state_json = json.dumps(state)

        if REDIS_AVAILABLE:
            # Set with 30 minute TTL
            redis_client.setex(session_key, 1800, state_json)
        else:
            # Fallback to memory store (no TTL in testing)
            _memory_store[session_key] = state_json

        print(f"STATE|saved|key={session_key}|fields={list(state.keys())}")
        return True

    except Exception as e:
        print(f"STATE|error_saving|key={session_key}|error={str(e)}")
        return False
