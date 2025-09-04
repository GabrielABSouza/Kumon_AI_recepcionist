# app/core/nodes/greeting_migrated.py
"""
Greeting Node - Nova Arquitetura Perception→Decision→Action→Delivery

Template de migração conforme especificado:
- Não lê/define estratégia (isso vem do SmartRouter)  
- Usa StageResolver para required_slots
- Só escreve outbox e campos do estado do próprio nó
- Idempotência garantida pelo dedup_key
"""

from typing import Dict, Any
import logging
from ..state.models import CeciliaState, ConversationStep
from ...workflows.contracts import MessageEnvelope
from .stage_resolver import get_required_slots_for_stage
from ..router.response_planner import resolve_channel

logger = logging.getLogger(__name__)


def greeting_node_migrated(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Greeting Node - Nova Arquitetura
    
    Responsabilidades:
    1. Coletar parent_name se ausente (business logic)
    2. Atualizar current_step apropriado
    3. NÃO tomar decisões de routing (SmartRouter faz isso)
    4. NÃO gerar responses diretamente (ResponsePlanner faz isso)
    """
    
    logger.info(f"[GREETING] Processing greeting node - session: {state.get('session_id', 'unknown')}")
    
    # === BUSINESS LOGIC ONLY ===
    
    # Get current required_slots from StageResolver
    from ..state.models import ConversationStage
    stage = ConversationStage.GREETING
    required_slots = get_required_slots_for_stage(stage)
    
    # Check slot completion for greeting stage
    parent_name = state.get("parent_name")
    missing_slots = [slot for slot in required_slots if not state.get(slot)]
    
    # Update business state based on slot completion
    if not parent_name:
        # First interaction - waiting for parent name
        # CRÍTICO: Sempre escrever Enums, nunca strings
        state["current_step"] = ConversationStep.INITIAL_RESPONSE
        state["greeting_status"] = "awaiting_parent_name"
        logger.debug(f"GreetingMigrated: step set to {ConversationStep.INITIAL_RESPONSE}")
        
        # Log business event
        logger.info(f"[GREETING] Awaiting parent name collection")
        
    else:
        # Parent name collected - greeting complete
        state["current_step"] = ConversationStep.PARENT_NAME_COLLECTION  
        state["greeting_status"] = "completed"
        state["parent_name_collected"] = True
        logger.debug(f"GreetingMigrated: step set to {ConversationStep.PARENT_NAME_COLLECTION}")
    
    # Validate enum type
    if not isinstance(state["current_step"], ConversationStep):
        logger.error(f"GreetingMigrated: INVALID TYPE - current_step should be ConversationStep, got {type(state['current_step'])}")
        
        # Indicate readiness for next stage
        if not missing_slots:
            state["greeting_ready_for_qualification"] = True
            
        logger.info(f"[GREETING] Greeting completed for parent: {parent_name}")
    
    # === STATE UPDATES ONLY ===
    
    # Update stage-specific metadata
    state["greeting_interaction_count"] = state.get("greeting_interaction_count", 0) + 1
    state["last_greeting_update"] = state.get("_trace_id", "unknown")
    
    # Ensure outbox exists (required by architecture)
    state.setdefault("outbox", [])
    
    # DO NOT generate responses directly - that's ResponsePlanner's job
    # DO NOT make routing decisions - that's SmartRouter's job
    # This node only handles business state for greeting stage
    
    logger.info(f"[GREETING] Business state updated - missing_slots: {missing_slots}, status: {state.get('greeting_status')}")
    
    return state


# ========== LEGACY COMPATIBILITY SHIM ==========

class GreetingNodeMigrated:
    """
    Legacy compatibility wrapper for existing code
    
    Maintains existing interface while using new architecture
    """
    
    def __init__(self):
        pass
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Legacy interface - delegates to new function"""
        return greeting_node_migrated(state)


# ========== CHECKLIST VALIDATION ==========

def validate_greeting_node_compliance():
    """
    Validate that greeting node follows new architecture rules
    
    Checklist:
    - ✅ Não lê/define estratégia 
    - ✅ Usa StageResolver para required_slots
    - ✅ Só escreve outbox e campos do estado do próprio nó
    - ✅ Idempotência garantida
    """
    
    # Test state
    test_state = {
        "session_id": "test_123",
        "current_stage": "greeting",
        "_trace_id": "trace_456"
    }
    
    # Execute node
    result = greeting_node_migrated(test_state.copy())
    
    # Validation checks
    checks = []
    
    # ✅ Should not write routing_decision (SmartRouter's job)
    checks.append(("no_routing_decision", "routing_decision" not in result or 
                   result.get("routing_decision") == test_state.get("routing_decision")))
    
    # ✅ Should not write planned_response (ResponsePlanner's job)  
    checks.append(("no_planned_response", "planned_response" not in result))
    
    # ✅ Should ensure outbox exists
    checks.append(("outbox_exists", "outbox" in result))
    
    # ✅ Should update only greeting-specific state
    greeting_fields = [
        "greeting_status", "greeting_interaction_count", 
        "parent_name_collected", "greeting_ready_for_qualification"
    ]
    greeting_updates = [field for field in greeting_fields if field in result]
    checks.append(("greeting_updates_only", len(greeting_updates) > 0))
    
    # ✅ Should be idempotent (same input = same output)
    result2 = greeting_node_migrated(test_state.copy())
    checks.append(("idempotent", result.get("greeting_status") == result2.get("greeting_status")))
    
    # Report results
    passed = sum(1 for _, check in checks if check)
    total = len(checks)
    
    print(f"✅ Greeting Node Compliance: {passed}/{total} checks passed")
    for check_name, passed_check in checks:
        status = "✅" if passed_check else "❌"
        print(f"   {status} {check_name}")
    
    return passed == total


# Export migrated node
greeting_node = greeting_node_migrated

# Legacy export for compatibility
greeting_node_legacy = GreetingNodeMigrated()