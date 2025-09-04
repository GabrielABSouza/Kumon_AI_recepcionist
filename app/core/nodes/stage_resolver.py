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
from ..state.models import CeciliaState, ConversationStage, ConversationStep, safe_update_state
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
        ConversationStage.UNSET: [],  # Estado inicial neutro
        ConversationStage.GREETING: ["parent_name"],
        ConversationStage.QUALIFICATION: ["parent_name", "child_name", "student_age", "education_level"],
        ConversationStage.INFORMATION_GATHERING: ["programs_of_interest"],
        ConversationStage.SCHEDULING: ["date_preferences", "available_slots"],
        ConversationStage.CONFIRMATION: ["selected_slot", "contact_email"],
        ConversationStage.COMPLETED: [],
        ConversationStage.HANDOFF: []
    }
    
    return stage_slots.get(stage, [])


class StageResolver:
    """StageResolver V2 - Define contexto inicial para estados neutros"""
    
    @staticmethod
    def apply(state: CeciliaState) -> CeciliaState:
        """
        Define stage inicial para estado V2 neutro
        
        1) Se já há stage em andamento e slots faltando, mantém
        2) Sessão nova (UNSET) → define greeting como contexto inicial  
        3) Preenche required_slots a partir do stage atual
        """
        try:
            current_stage = state.get("current_stage")
            current_step = state.get("current_step")
            
            # 1) Se já há stage em andamento e slots faltando, mantém
            if (current_stage not in (ConversationStage.UNSET, None) and 
                current_stage != ConversationStage.UNSET.value and
                state.get("required_slots")):
                logger.info(f"StageResolver.apply: mantendo stage={current_stage} (slots em andamento)")
                return state

            # 2) Sessão nova → define greeting como contexto inicial
            if (current_stage in (ConversationStage.UNSET, ConversationStage.UNSET.value, None) or
                current_step in (ConversationStep.NONE, ConversationStep.NONE.value, None)):
                
                logger.info("StageResolver.apply: sessão nova → definindo contexto inicial greeting")
                
                safe_update_state(state, {
                    "current_stage": ConversationStage.GREETING,
                    "current_step": ConversationStep.WELCOME
                })
                
            # 3) Preencher required_slots a partir do stage atual
            resolved_stage = ConversationStage(state["current_stage"])
            required_slots = get_required_slots_for_stage(resolved_stage)
            
            safe_update_state(state, {
                "required_slots": required_slots
            })
            
            logger.info(f"StageResolver.apply: resolved stage={resolved_stage.value}, step={state['current_step']}, slots={len(required_slots)}")
            
            return state
            
        except Exception as e:
            logger.error(f"StageResolver.apply error: {e}")
            
            # Fallback seguro
            safe_update_state(state, {
                "current_stage": ConversationStage.GREETING,
                "current_step": ConversationStep.WELCOME,
                "required_slots": ["parent_name"]
            })
            
            return state


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
        
        # CRÍTICO: Sempre escrever Enums, nunca strings
        state["current_stage"] = inferred_stage  # Enum instance
        state["required_slots"] = get_required_slots_for_stage(inferred_stage)
        
        # Debug logging to confirm enum types
        logger.debug(f"StageResolver: stage type={type(state['current_stage'])}, value={state['current_stage']}")
        if not isinstance(state["current_stage"], ConversationStage):
            logger.error(f"StageResolver: INVALID TYPE - stage should be ConversationStage, got {type(state['current_stage'])}")
        
        # Garantir outbox exists
        state.setdefault("outbox", [])
        
        logger.info(f"StageResolver: stage={inferred_stage.value}, slots={len(state['required_slots'])}")
        
        return state
        
    except Exception as e:
        logger.error(f"StageResolver error: {e}")
        
        # Fallback seguro - SEMPRE Enum
        state["current_stage"] = ConversationStage.GREETING  # Enum instance
        state["required_slots"] = ["parent_name"]
        state.setdefault("outbox", [])
        
        logger.warning(f"StageResolver: fallback applied, stage type={type(state['current_stage'])}")
        
        return state