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


def get_conversation_history(phone: str, limit: int = 4) -> list:
    """
    Retrieve conversation history for a phone number.
    
    Args:
        phone: Phone number to get history for
        limit: Maximum number of recent messages to return
        
    Returns:
        List of message dictionaries with 'role' and 'content' fields
    """
    if not phone:
        return []
    
    try:
        # Get stored messages for this phone number
        messages = _get_stored_messages(phone)
        
        # Return the most recent messages up to the limit
        recent_messages = messages[-limit:] if len(messages) > limit else messages
        
        # Format for Gemini context (remove timestamp, keep role/content)
        formatted_messages = []
        for msg in recent_messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return formatted_messages
        
    except Exception as e:
        print(f"HISTORY|error_loading|phone={phone}|error={str(e)}")
        return []


def _get_stored_messages(phone: str) -> list:
    """
    Internal function to retrieve stored messages from persistence layer.
    
    This is a placeholder that simulates message storage.
    In a real implementation, this would query the PostgreSQL conversation_messages table.
    
    Args:
        phone: Phone number to get messages for
        
    Returns:
        List of message dictionaries with timestamp, role, and content
    """
    # Remove + prefix for consistent key format
    history_key = f"conversation_history:{phone.lstrip('+')}"
    
    try:
        if REDIS_AVAILABLE:
            # Try to get from Redis
            history_json = redis_client.get(history_key)
            if history_json:
                return json.loads(history_json)
        else:
            # Fallback to memory store for testing
            history_json = _memory_store.get(history_key)
            if history_json:
                return json.loads(history_json)
                
    except Exception as e:
        print(f"HISTORY|error_retrieving|key={history_key}|error={str(e)}")
    
    return []


def save_message_to_history(phone: str, role: str, content: str) -> bool:
    """
    Save a message to conversation history.
    
    Args:
        phone: Phone number
        role: 'user' or 'assistant' 
        content: Message content
        
    Returns:
        True if saved successfully
    """
    if not phone or not role or not content:
        return False
    
    # Remove + prefix for consistent key format
    history_key = f"conversation_history:{phone.lstrip('+')}"
    
    try:
        # Get existing history
        existing_messages = _get_stored_messages(phone)
        
        # Create new message with timestamp
        from datetime import datetime
        new_message = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "role": role,
            "content": content
        }
        
        # Add to history (keep last 20 messages max)
        existing_messages.append(new_message)
        if len(existing_messages) > 20:
            existing_messages = existing_messages[-20:]  # Keep only last 20
        
        # Save back to storage
        history_json = json.dumps(existing_messages)
        
        if REDIS_AVAILABLE:
            # Set with 24 hour TTL for history
            redis_client.setex(history_key, 86400, history_json)
        else:
            # Fallback to memory store
            _memory_store[history_key] = history_json
        
        print(f"HISTORY|saved|phone={phone}|role={role}|total_messages={len(existing_messages)}")
        return True
        
    except Exception as e:
        print(f"HISTORY|error_saving|phone={phone}|error={str(e)}")
        return False
