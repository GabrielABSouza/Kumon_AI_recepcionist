"""
CeciliaState - Optimized State Definition for LangGraph Kumon Assistant

Solução otimizada seguindo rigorosamente state_solving.md:
- Separação clara de responsabilidades 
- Apenas 12 campos core obrigatórios
- Subsistemas opcionais com total=False
- Performance e manutenibilidade melhoradas
"""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from langgraph.graph import add_messages


class ConversationStage(str, Enum):
    """Estados principais da conversa"""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION_GATHERING = "information_gathering"
    SCHEDULING = "scheduling"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


class ConversationStep(str, Enum):
    """Passos específicos dentro de cada estágio"""
    # Greeting steps
    WELCOME = "welcome"
    INITIAL_RESPONSE = "initial_response"
    PARENT_NAME_COLLECTION = "parent_name_collection"
    CHILD_NAME_COLLECTION = "child_name_collection"
    
    # Qualification steps  
    CHILD_AGE_INQUIRY = "child_age_inquiry"
    CURRENT_SCHOOL_GRADE = "current_school_grade"
    
    # Information gathering steps
    METHODOLOGY_EXPLANATION = "methodology_explanation"
    PROGRAM_DETAILS = "program_details"
    
    # Scheduling steps
    AVAILABILITY_CHECK = "availability_check"
    APPOINTMENT_SUGGESTION = "appointment_suggestion"
    DATE_PREFERENCE = "date_preference"
    TIME_SELECTION = "time_selection"
    EMAIL_COLLECTION = "email_collection"
    EVENT_CREATION = "event_creation"
    
    # Final steps
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    CONVERSATION_ENDED = "conversation_ended"


class CollectedData(TypedDict, total=False):
    """Dados coletados pelo agente durante o fluxo"""
    # Saudação
    parent_name: str
    child_name: str  
    is_for_self: bool
    
    # Qualificação
    student_age: int
    education_level: str
    
    # Information Gathering
    programs_of_interest: List[str]
    
    # Scheduling
    date_preferences: Dict[str, Any]
    available_slots: List[Dict[str, Any]]
    selected_slot: Dict[str, Any]
    
    # Confirmation
    contact_email: str


class ConversationMetrics(TypedDict):
    """Métricas para failure detection e recovery"""
    failed_attempts: int
    consecutive_confusion: int
    same_question_count: int
    message_count: int
    created_at: datetime
    last_successful_collection: Optional[str]
    problematic_fields: List[str]


class DataValidation(TypedDict):
    """Sistema de validação e tracking"""
    extraction_attempts: Dict[str, int]      # {"student_age": 1, "contact_email": 2}
    pending_confirmations: List[str]         # ["contact_email"] - aguardando confirmação
    validation_history: List[Dict[str, Any]] # Para auditoria
    last_extraction_error: Optional[str]    # Para debugging


class DecisionTrail(TypedDict):
    """Auditoria de decisões para debugging"""
    last_decisions: List[Dict[str, Any]]     # Histórico de transições
    edge_function_calls: List[str]          # Funções de roteamento chamadas
    validation_failures: List[Dict[str, Any]] # Falhas de validação


class CeciliaState(TypedDict):
    """Estado principal otimizado do LangGraph"""
    
    # IDENTIFICAÇÃO (automática do WhatsApp)
    phone_number: str
    conversation_id: str
    
    # CONTROLE DE FLUXO (gerenciado pelo sistema)
    current_stage: ConversationStage
    current_step: ConversationStep
    messages: Annotated[List[Dict[str, Any]], add_messages]
    last_user_message: str
    
    # DADOS COLETADOS (seguindo o fluxo definido)
    collected_data: CollectedData
    
    # SISTEMA DE VALIDAÇÃO
    data_validation: DataValidation
    
    # MÉTRICAS E AUDITORIA
    conversation_metrics: ConversationMetrics
    decision_trail: DecisionTrail


# ========== STATE UTILITIES ==========
def create_initial_cecilia_state(phone_number: str, user_message: str = "") -> CeciliaState:
    """
    Create initial CeciliaState following state_solving.md
    
    Apenas 12 campos core obrigatórios, subsistemas inicializados vazios
    """
    now = datetime.now(timezone.utc)
    conversation_id = f"conv_{phone_number}_{now.strftime('%Y%m%d_%H%M%S')}"
    
    return CeciliaState(
        # IDENTIFICAÇÃO
        phone_number=phone_number,
        conversation_id=conversation_id,
        
        # CONTROLE DE FLUXO
        current_stage=ConversationStage.GREETING,
        current_step=ConversationStep.WELCOME,
        messages=[{"role": "user", "content": user_message, "timestamp": now.isoformat()}] if user_message else [],
        last_user_message=user_message,
        
        # DADOS COLETADOS (vazio inicialmente)
        collected_data=CollectedData(),
        
        # SISTEMA DE VALIDAÇÃO (inicializado)
        data_validation=DataValidation(
            extraction_attempts={},
            pending_confirmations=[],
            validation_history=[],
            last_extraction_error=None
        ),
        
        # MÉTRICAS (inicializadas)
        conversation_metrics=ConversationMetrics(
            failed_attempts=0,
            consecutive_confusion=0,
            same_question_count=0,
            message_count=1 if user_message else 0,
            created_at=now,
            last_successful_collection=None,
            problematic_fields=[]
        ),
        
        # AUDITORIA (inicializada)
        decision_trail=DecisionTrail(
            last_decisions=[],
            edge_function_calls=[],
            validation_failures=[]
        )
    )


# ========== COMPATIBILITY FUNCTIONS ==========
def get_collected_field(state: CeciliaState, field_name: str) -> Any:
    """Helper para acessar campos coletados com segurança"""
    return state["collected_data"].get(field_name)


def set_collected_field(state: CeciliaState, field_name: str, value: Any) -> None:
    """Helper para definir campos coletados"""
    state["collected_data"][field_name] = value


def increment_metric(state: CeciliaState, metric_name: str, amount: int = 1) -> None:
    """Helper para incrementar métricas"""
    current_value = state["conversation_metrics"].get(metric_name, 0)
    state["conversation_metrics"][metric_name] = current_value + amount


def add_decision_to_trail(state: CeciliaState, decision: Dict[str, Any]) -> None:
    """Helper para adicionar decisão ao trail"""
    state["decision_trail"]["last_decisions"].append({
        **decision,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Manter apenas últimas 10 decisões
    if len(state["decision_trail"]["last_decisions"]) > 10:
        state["decision_trail"]["last_decisions"] = state["decision_trail"]["last_decisions"][-10:]


def add_validation_failure(state: CeciliaState, failure: Dict[str, Any]) -> None:
    """Helper para registrar falha de validação"""
    state["decision_trail"]["validation_failures"].append({
        **failure,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Manter apenas últimas 5 falhas
    if len(state["decision_trail"]["validation_failures"]) > 5:
        state["decision_trail"]["validation_failures"] = state["decision_trail"]["validation_failures"][-5:]


def safe_update_state(state: CeciliaState, updates: Dict[str, Any]) -> None:
    """
    Safely update CeciliaState without converting to dict
    
    CRITICAL: This preserves TypedDict structure. Using .update() converts
    CeciliaState to plain dict and breaks attribute access in LangGraph nodes.
    
    Args:
        state: The CeciliaState to update (modified in place)
        updates: Dictionary of updates to apply
    """
    for key, value in updates.items():
        state[key] = value