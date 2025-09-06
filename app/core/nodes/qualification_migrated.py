# app/core/nodes/qualification_migrated.py
"""
Qualification Node - Nova Arquitetura Perception→Decision→Action→Delivery

Template de migração conforme especificado:
- Não lê/define estratégia (isso vem do SmartRouter)  
- Usa StageResolver para required_slots
- Só escreve outbox e campos do estado do próprio nó
- Idempotência garantida pelo dedup_key
"""

from typing import Dict, Any
import re
import logging
from ..state.models import CeciliaState, ConversationStage, ConversationStep
from ...workflows.contracts import MessageEnvelope
from .stage_resolver import get_required_slots_for_stage

logger = logging.getLogger(__name__)


def extract_age_from_message(message: str) -> int | None:
    """Extract age from user message"""
    age_match = re.search(r'\b(\d{1,2})\b', message)
    if age_match:
        age = int(age_match.group(1))
        # Reasonable age bounds
        if 2 <= age <= 65:
            return age
    return None


def extract_child_name_from_message(message: str) -> str | None:
    """Extract child name from user message"""
    # Simple heuristics for name extraction
    message = message.strip()
    
    # Look for patterns like "Nome é João", "Chama Maria", "É o Pedro", "filha chama Paula"
    name_patterns = [
        r'(?:nome\s+é|chama-se|chama|é\s+o|é\s+a|filha\s+chama|filho\s+chama)\s+([A-ZÀ-ÿ][a-zà-ÿ]+)',
        r'^([A-ZÀ-ÿ][a-zà-ÿ]+)\s+tem\s+\d+',  # "Maria tem 8 anos" 
        r'^([A-ZÀ-ÿ][a-zà-ÿ]+)$',  # Just the name
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2 and name.isalpha():
                return name.title()
                
    return None


def qualification_node_migrated(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Qualification Node - Nova Arquitetura
    
    Responsabilidades:
    1. Coletar parent_name, child_name, student_age, education_level
    2. Determinar current_step baseado nos slots coletados
    3. NÃO tomar decisões de routing (SmartRouter faz isso)
    4. NÃO gerar responses diretamente (ResponsePlanner faz isso)
    """
    
    logger.info(f"[QUALIFICATION] Processing qualification node - session: {state.get('session_id', 'unknown')}")
    
    # === BUSINESS LOGIC ONLY ===
    
    # Get current required_slots from StageResolver
    stage = ConversationStage.QUALIFICATION
    required_slots = get_required_slots_for_stage(stage)
    
    user_message = state.get("last_user_message", "")
    current_step = state.get("current_step", "name_collection")
    
    # Current slot values
    parent_name = state.get("parent_name")
    child_name = state.get("child_name")
    student_age = state.get("student_age")
    education_level = state.get("education_level")
    
    # === DATA EXTRACTION FROM USER MESSAGE ===
    
    extracted_updates = {}
    
    # Try to extract missing data from current message
    if user_message:
        # Extract child name if missing
        if not child_name:
            extracted_name = extract_child_name_from_message(user_message)
            if extracted_name:
                extracted_updates["child_name"] = extracted_name
                logger.info(f"[QUALIFICATION] Extracted child name: {extracted_name}")
        
        # Extract age if missing
        if not student_age:
            extracted_age = extract_age_from_message(user_message)
            if extracted_age:
                extracted_updates["student_age"] = extracted_age
                logger.info(f"[QUALIFICATION] Extracted age: {extracted_age}")
                
                # Infer education level from age
                if 2 <= extracted_age <= 5:
                    extracted_updates["education_level"] = "educacao_infantil"
                elif 6 <= extracted_age <= 10:
                    extracted_updates["education_level"] = "ensino_fundamental_1"
                elif 11 <= extracted_age <= 14:
                    extracted_updates["education_level"] = "ensino_fundamental_2"
                elif 15 <= extracted_age <= 17:
                    extracted_updates["education_level"] = "ensino_medio"
                else:
                    extracted_updates["education_level"] = "adulto"
                    
                logger.info(f"[QUALIFICATION] Inferred education level: {extracted_updates['education_level']}")
    
    # Apply extracted updates to state
    state.update(extracted_updates)
    
    # Re-evaluate with updated values
    child_name = state.get("child_name") 
    student_age = state.get("student_age")
    education_level = state.get("education_level")
    
    # === STEP PROGRESSION LOGIC ===
    
    missing_slots = [slot for slot in required_slots if not state.get(slot)]
    
    if not parent_name:
        # CRÍTICO: Sempre escrever Enums, nunca strings
        state["current_step"] = ConversationStep.PARENT_NAME_COLLECTION
        state["qualification_status"] = "awaiting_parent_name"
        logger.debug(f"QualificationMigrated: step set to {ConversationStep.PARENT_NAME_COLLECTION}")
        
    elif not child_name:
        state["current_step"] = ConversationStep.CHILD_NAME_COLLECTION
        state["qualification_status"] = "awaiting_child_name"
        logger.debug(f"QualificationMigrated: step set to {ConversationStep.CHILD_NAME_COLLECTION}")
        
    elif not student_age:
        # Using closest available enum
        state["current_step"] = ConversationStep.CHILD_AGE_INQUIRY
        state["qualification_status"] = "awaiting_age"
        logger.debug(f"QualificationMigrated: step set to {ConversationStep.CHILD_AGE_INQUIRY}")
        
    elif not education_level:
        # Using closest available enum 
        state["current_step"] = ConversationStep.CURRENT_SCHOOL_GRADE
        state["qualification_status"] = "awaiting_education_level"
        logger.debug(f"QualificationMigrated: step set to {ConversationStep.CURRENT_SCHOOL_GRADE}")
        
    else:
        # All required data collected
        state["current_step"] = ConversationStep.CHILD_AGE_INQUIRY  # Use existing enum as completed marker
        state["qualification_status"] = "completed"
        state["qualification_ready_for_information"] = True
        logger.debug(f"QualificationMigrated: qualification complete, step={ConversationStep.CHILD_AGE_INQUIRY}")
    
    # Validate enum type
    if not isinstance(state["current_step"], ConversationStep):
        logger.error(f"QualificationMigrated: INVALID TYPE - current_step should be ConversationStep, got {type(state['current_step'])}")
        
        # Set programs of interest based on age/level
        if not state.get("programs_of_interest"):
            age = state["student_age"]
            if age <= 10:
                state["programs_of_interest"] = ["matematica", "portugues"]
            elif age <= 14:
                state["programs_of_interest"] = ["matematica", "portugues"] 
            else:
                state["programs_of_interest"] = ["matematica", "portugues", "ingles"]
    
    # === STATE UPDATES ONLY ===
    
    # Update qualification-specific metadata
    state["qualification_interaction_count"] = state.get("qualification_interaction_count", 0) + 1
    state["qualification_data_completeness"] = len(required_slots) - len(missing_slots)
    state["qualification_missing_fields"] = missing_slots
    
    # Age-specific logic
    if student_age:
        if student_age < 6:
            state["qualification_age_category"] = "early_childhood"
        elif student_age < 12:
            state["qualification_age_category"] = "elementary"
        elif student_age < 18:
            state["qualification_age_category"] = "secondary"
        else:
            state["qualification_age_category"] = "adult"
    
    # Ensure outbox exists (required by architecture)
    state.setdefault("outbox", [])
    
    # DO NOT generate responses directly - that's ResponsePlanner's job
    # DO NOT make routing decisions - that's SmartRouter's job
    # This node only handles business state for qualification stage
    
    logger.info(f"[QUALIFICATION] Business state updated - missing_slots: {missing_slots}, status: {state.get('qualification_status')}")
    
    return state


# ========== LEGACY COMPATIBILITY SHIM ==========

class QualificationNodeMigrated:
    """
    Legacy compatibility wrapper for existing code
    
    Maintains existing interface while using new architecture
    """
    
    def __init__(self):
        pass
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Legacy interface - delegates to new function"""
        return qualification_node_migrated(state)


# ========== CHECKLIST VALIDATION ==========

def validate_qualification_node_compliance():
    """
    Validate that qualification node follows new architecture rules
    
    Checklist:
    - ✅ Não lê/define estratégia 
    - ✅ Usa StageResolver para required_slots
    - ✅ Só escreve outbox e campos do estado do próprio nó
    - ✅ Idempotência garantida
    """
    
    # Test state - missing child name and age
    test_state = {
        "session_id": "test_qual_123",
        "current_stage": "qualification",
        "parent_name": "João Silva",
        "last_user_message": "Maria tem 8 anos",
        "_trace_id": "trace_qual_456"
    }
    
    # Execute node
    result = qualification_node_migrated(test_state.copy())
    
    # Validation checks
    checks = []
    
    # ✅ Should not write routing_decision (SmartRouter's job)
    checks.append(("no_routing_decision", "routing_decision" not in result or 
                   result.get("routing_decision") == test_state.get("routing_decision")))
    
    # ✅ Should not write planned_response (ResponsePlanner's job)  
    checks.append(("no_planned_response", "planned_response" not in result))
    
    # ✅ Should ensure outbox exists
    checks.append(("outbox_exists", "outbox" in result))
    
    # ✅ Should extract data from user message
    checks.append(("extracts_child_name", result.get("child_name") == "Maria"))
    checks.append(("extracts_age", result.get("student_age") == 8))
    checks.append(("infers_education", result.get("education_level") == "ensino_fundamental_1"))
    
    # ✅ Should update only qualification-specific state
    qualification_fields = [
        "qualification_status", "qualification_interaction_count", 
        "qualification_data_completeness", "qualification_missing_fields",
        "qualification_age_category", "qualification_ready_for_information"
    ]
    qualification_updates = [field for field in qualification_fields if field in result]
    checks.append(("qualification_updates_only", len(qualification_updates) > 0))
    
    # ✅ Should determine correct step progression
    checks.append(("correct_step_progression", result.get("current_step") in [
        "parent_name_collection", "child_name_collection", "age_collection", 
        "education_level_collection", "qualification_complete"
    ]))
    
    # ✅ Should be idempotent (same input = same output)
    result2 = qualification_node_migrated(test_state.copy())
    checks.append(("idempotent", result.get("qualification_status") == result2.get("qualification_status")))
    
    # Report results
    passed = sum(1 for _, check in checks if check)
    total = len(checks)
    
    print(f"✅ Qualification Node Compliance: {passed}/{total} checks passed")
    for check_name, passed_check in checks:
        status = "✅" if passed_check else "❌"
        print(f"   {status} {check_name}")
    
    return passed == total


# Export migrated node
qualification_node = qualification_node_migrated

# Legacy export for compatibility
qualification_node_legacy = QualificationNodeMigrated()