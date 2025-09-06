"""
Workflow Guards - Anti-recursion and loop prevention
Prevents infinite loops and excessive recursion in conversation workflows
"""

import logging
import time
from typing import Optional, Dict, Any
from .cache_manager import get_redis

logger = logging.getLogger(__name__)

# Configuration
MAX_RECURSION_LIMIT = 8  # Maximum workflow steps per conversation
RECENT_GREETING_WINDOW_SEC = 30  # Window to prevent greeting loops
GREETING_COOLDOWN_KEY = "recent_greeting"
RECURSION_COUNTER_KEY = "recursion_count"
WORKFLOW_STATE_KEY = "workflow_state"


def check_recursion_limit(conversation_id: str, stage: str = None) -> bool:
    """
    Check if conversation has exceeded recursion limits
    
    Args:
        conversation_id: Unique conversation identifier
        stage: Current workflow stage
        
    Returns:
        bool: True if within limits, False if limit exceeded
    """
    redis = get_redis()
    if not redis:
        # Without Redis, allow processing but log warning
        logger.warning(f"RECURSION_CHECK|no_redis|conv={conversation_id}|allowing_processing")
        return True
    
    try:
        counter_key = f"{RECURSION_COUNTER_KEY}:{conversation_id}"
        
        # Get current count
        current_count = redis.get(counter_key)
        count = int(current_count) if current_count else 0
        
        if count >= MAX_RECURSION_LIMIT:
            logger.error(f"RECURSION_LIMIT|exceeded|conv={conversation_id}|count={count}|stage={stage}")
            return False
        
        # Increment counter with TTL (reset after 5 minutes of inactivity)
        redis.incr(counter_key)
        redis.expire(counter_key, 300)  # 5 minutes
        
        logger.info(f"RECURSION_CHECK|within_limit|conv={conversation_id}|count={count + 1}|stage={stage}")
        return True
        
    except Exception as e:
        logger.error(f"RECURSION_CHECK|error|conv={conversation_id}|error={e}")
        # On error, allow processing
        return True


def prevent_greeting_loops(phone: str, stage: str, intent: str = None) -> bool:
    """
    Prevent greeting loops by checking recent greeting deliveries
    
    Args:
        phone: Phone number
        stage: Current workflow stage  
        intent: Detected intent (if available)
        
    Returns:
        bool: True if should proceed, False if should block (greeting loop)
    """
    redis = get_redis()
    if not redis:
        return True
    
    # Only check for greeting stage with greeting intent
    if stage != "greeting" or intent != "greeting":
        return True
    
    try:
        greeting_key = f"{GREETING_COOLDOWN_KEY}:{phone}"
        
        # Check if recent greeting was delivered
        recent_greeting = redis.get(greeting_key)
        if recent_greeting:
            logger.warning(f"GREETING_LOOP|blocked|phone={phone[-4:]}|recent_delivery_detected")
            return False
        
        # Mark greeting as delivered (prevent loops for next 30 seconds)
        redis.setex(greeting_key, RECENT_GREETING_WINDOW_SEC, "1")
        
        logger.info(f"GREETING_LOOP|allowed|phone={phone[-4:]}|cooldown_set={RECENT_GREETING_WINDOW_SEC}s")
        return True
        
    except Exception as e:
        logger.error(f"GREETING_LOOP|error|phone={phone[-4:]}|error={e}")
        # On error, allow processing
        return True


def check_workflow_state_consistency(conversation_id: str, current_stage: str, expected_transitions: list) -> bool:
    """
    Check if workflow state transitions are consistent
    
    Args:
        conversation_id: Conversation identifier
        current_stage: Current stage being entered
        expected_transitions: List of valid previous stages
        
    Returns:
        bool: True if transition is valid
    """
    redis = get_redis()
    if not redis:
        return True
    
    try:
        state_key = f"{WORKFLOW_STATE_KEY}:{conversation_id}"
        
        # Get previous stage
        previous_stage = redis.get(state_key)
        if not previous_stage:
            # First stage is always valid
            redis.setex(state_key, 300, current_stage)  # 5 minutes TTL
            logger.info(f"WORKFLOW_STATE|initial|conv={conversation_id}|stage={current_stage}")
            return True
        
        previous_stage = previous_stage.decode() if isinstance(previous_stage, bytes) else previous_stage
        
        # Check if transition is valid
        if previous_stage not in expected_transitions and expected_transitions:
            logger.warning(f"WORKFLOW_STATE|invalid_transition|conv={conversation_id}|from={previous_stage}|to={current_stage}|expected={expected_transitions}")
            # Log but allow - don't block workflow
        
        # Update state
        redis.setex(state_key, 300, current_stage)
        logger.info(f"WORKFLOW_STATE|transition|conv={conversation_id}|from={previous_stage}|to={current_stage}")
        return True
        
    except Exception as e:
        logger.error(f"WORKFLOW_STATE|error|conv={conversation_id}|error={e}")
        return True


def reset_conversation_guards(conversation_id: str, phone: str = None):
    """
    Reset all guard counters for a conversation (for cleanup/debugging)
    
    Args:
        conversation_id: Conversation identifier
        phone: Phone number (optional, for greeting reset)
    """
    redis = get_redis()
    if not redis:
        return
    
    try:
        keys_to_delete = [
            f"{RECURSION_COUNTER_KEY}:{conversation_id}",
            f"{WORKFLOW_STATE_KEY}:{conversation_id}",
        ]
        
        if phone:
            keys_to_delete.append(f"{GREETING_COOLDOWN_KEY}:{phone}")
        
        deleted = redis.delete(*keys_to_delete)
        logger.info(f"GUARDS_RESET|conv={conversation_id}|deleted_keys={deleted}")
        
    except Exception as e:
        logger.error(f"GUARDS_RESET|error|conv={conversation_id}|error={e}")


def get_guard_stats(conversation_id: str, phone: str = None) -> Dict[str, Any]:
    """
    Get current guard statistics for debugging
    
    Args:
        conversation_id: Conversation identifier
        phone: Phone number (optional)
        
    Returns:
        Dict with current guard states
    """
    redis = get_redis()
    if not redis:
        return {"error": "redis_unavailable"}
    
    try:
        stats = {}
        
        # Recursion count
        counter_key = f"{RECURSION_COUNTER_KEY}:{conversation_id}"
        count = redis.get(counter_key)
        stats["recursion_count"] = int(count) if count else 0
        stats["recursion_limit"] = MAX_RECURSION_LIMIT
        
        # Workflow state
        state_key = f"{WORKFLOW_STATE_KEY}:{conversation_id}"
        current_state = redis.get(state_key)
        stats["current_workflow_state"] = current_state.decode() if current_state else None
        
        # Greeting cooldown
        if phone:
            greeting_key = f"{GREETING_COOLDOWN_KEY}:{phone}"
            cooldown = redis.ttl(greeting_key)
            stats["greeting_cooldown_ttl"] = cooldown if cooldown > 0 else 0
        
        return stats
        
    except Exception as e:
        logger.error(f"GUARD_STATS|error|conv={conversation_id}|error={e}")
        return {"error": str(e)}


def configure_recursion_limit(new_limit: int) -> bool:
    """
    Configure recursion limit (for testing/debugging)
    
    Args:
        new_limit: New recursion limit
        
    Returns:
        bool: True if set successfully
    """
    global MAX_RECURSION_LIMIT
    
    if new_limit < 1 or new_limit > 50:
        logger.error(f"CONFIGURE_LIMIT|invalid_limit|limit={new_limit}")
        return False
    
    old_limit = MAX_RECURSION_LIMIT
    MAX_RECURSION_LIMIT = new_limit
    logger.info(f"CONFIGURE_LIMIT|updated|old={old_limit}|new={new_limit}")
    return True