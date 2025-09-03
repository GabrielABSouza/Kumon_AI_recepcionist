# app/core/nodes/stage_resolver.py
"""
StageResolver - Fonte Única de required_slots e current_stage

Responsabilidades:
- Percepção: Analisar estado atual e definir stage apropriado
- Slots: Determinar required_slots baseado no stage e contexto
- Estado: Atualizar current_stage no state sem lógica de negócio
"""

from typing import Dict, Any
import logging
from ..state.models import CeciliaState, ConversationStage, ConversationStep
from ...graph.nodes import get_node_by_id, get_nodes_by_stage

logger = logging.getLogger(__name__)


def infer_stage_from_context(state: Dict[str, Any]) -> ConversationStage:
    """Infere stage baseado no contexto do estado atual"""
    
    # Se já existe current_stage válido, manter
    current_stage = state.get("current_stage")
    if current_stage:
        try:
            return ConversationStage(current_stage)
        except ValueError:
            logger.warning(f"Invalid current_stage: {current_stage}, inferring from context")
    
    # Inferência baseada em dados coletados
    parent_name = state.get("parent_name")
    child_name = state.get("child_name") 
    student_age = state.get("student_age")
    selected_slot = state.get("selected_slot")
    contact_email = state.get("contact_email")
    
    # Lógica de progressão natural
    if contact_email and selected_slot:
        return ConversationStage.CONFIRMATION
    elif student_age and parent_name and child_name:
        return ConversationStage.SCHEDULING  
    elif parent_name and child_name:
        return ConversationStage.INFORMATION_GATHERING
    elif parent_name:
        return ConversationStage.QUALIFICATION
    else:
        return ConversationStage.GREETING


def get_required_slots_for_stage(stage: ConversationStage) -> list[str]:
    """Retorna required_slots para um stage específico"""
    
    # Mapeamento baseado em app/graph/nodes.py business logic
    stage_slots = {
        ConversationStage.GREETING: ["parent_name"],
        ConversationStage.QUALIFICATION: ["parent_name", "child_name", "student_age", "education_level"],
        ConversationStage.INFORMATION_GATHERING: ["programs_of_interest"],
        ConversationStage.SCHEDULING: ["date_preferences", "available_slots"],
        ConversationStage.CONFIRMATION: ["selected_slot", "contact_email"],
        ConversationStage.COMPLETED: [],
        ConversationStage.HANDOFF: []
    }
    
    return stage_slots.get(stage, [])


def stage_resolver_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    StageResolver Node - Fonte única de stage e slots
    
    Responsabilidades:
    1. Inferir current_stage baseado no contexto
    2. Definir required_slots para o stage
    3. Garantir outbox existe no state
    4. Não tomar decisões de negócio
    """
    
    try:
        # Inferir stage apropriado
        inferred_stage = infer_stage_from_context(state)
        
        # Atualizar state
        state["current_stage"] = inferred_stage.value
        state["required_slots"] = get_required_slots_for_stage(inferred_stage)
        
        # Garantir outbox exists
        state.setdefault("outbox", [])
        
        logger.info(f"StageResolver: stage={inferred_stage.value}, slots={len(state['required_slots'])}")
        
        return state
        
    except Exception as e:
        logger.error(f"StageResolver error: {e}")
        
        # Fallback seguro
        state["current_stage"] = ConversationStage.GREETING.value
        state["required_slots"] = ["parent_name"]
        state.setdefault("outbox", [])
        
        return state