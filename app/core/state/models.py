"""
CeciliaState - Optimized State Definition for LangGraph Kumon Assistant

Solução otimizada seguindo rigorosamente state_solving.md:
- Separação clara de responsabilidades
- Apenas 12 campos core obrigatórios
- Subsistemas opcionais com total=False
- Performance e manutenibilidade melhoradas
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, TypedDict

try:
    from langgraph.graph import add_messages
except ImportError:
    # Fallback for older LangGraph versions
    def add_messages(x, y):
        return x + y


class ConversationStage(str, Enum):
    """Estados principais da conversa"""

    UNSET = "unset"  # Estado inicial neutro antes do StageResolver
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION_GATHERING = "information_gathering"
    SCHEDULING = "scheduling"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"
    HANDOFF = "handoff"


class ConversationStep(str, Enum):
    """Passos específicos dentro de cada estágio"""

    # Initial state
    NONE = "none"  # Estado inicial neutro antes do StageResolver

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
    PROGRAM_EXPLANATION = "program_explanation"

    # Scheduling steps
    AVAILABILITY_CHECK = "availability_check"
    APPOINTMENT_SUGGESTION = "appointment_suggestion"
    DATE_PREFERENCE = "date_preference"
    TIME_SELECTION = "time_selection"
    EMAIL_COLLECTION = "email_collection"
    EVENT_CREATION = "event_creation"
    SLOT_PRESENTATION = "slot_presentation"

    # Validation steps
    CONTACT_CONFIRMATION = "contact_confirmation"

    # Final steps
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    FINAL_CONFIRMATION = "final_confirmation"
    CONVERSATION_ENDED = "conversation_ended"
    HUMAN_TRANSFER = "human_transfer"


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

    extraction_attempts: Dict[str, int]  # {"student_age": 1, "contact_email": 2}
    pending_confirmations: List[str]  # ["contact_email"] - aguardando confirmação
    validation_history: List[Dict[str, Any]]  # Para auditoria
    last_extraction_error: Optional[str]  # Para debugging


class DecisionTrail(TypedDict):
    """Auditoria de decisões para debugging"""

    last_decisions: List[Dict[str, Any]]  # Histórico de transições
    edge_function_calls: List[str]  # Funções de roteamento chamadas
    validation_failures: List[Dict[str, Any]]  # Falhas de validação


class ErrorRecoveryState(TypedDict):
    """Sistema de tratamento de erros e recovery"""

    # Critical delivery errors
    critical_delivery_failure: bool
    critical_error: Optional[str]
    requires_manual_intervention: bool

    # Delivery errors
    delivery_failed: bool
    delivery_fallback_used: bool
    last_delivery_error: Optional[Dict[str, Any]]
    emergency_response_sent: bool

    # Validation errors
    validation_failed: bool
    validation_error: Optional[str]
    validation_failed_count: int

    # Recovery metadata
    recovery_attempts: int
    last_recovery_attempt: Optional[str]
    recovery_strategy: Optional[str]
    error_history: List[Dict[str, Any]]


class CeciliaState(TypedDict):
    """Estado principal otimizado do LangGraph"""

    # IDENTIFICAÇÃO (automática do WhatsApp)
    phone_number: str
    conversation_id: str
    session_id: str
    channel: str
    instance: str  # WhatsApp instance name (e.g., "kumon_assistant")

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

    # SISTEMA DE ERRO E RECOVERY
    error_recovery: ErrorRecoveryState


# ========== STATE UTILITIES ==========
def create_initial_cecilia_state(
    phone_number: str,
    user_message: str = "",
    channel: str = "whatsapp",
    instance: str = "",
) -> CeciliaState:
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
        session_id=conversation_id,  # Usar conversation_id como session_id
        channel=channel,
        instance=instance,  # WhatsApp instance from webhook
        # CONTROLE DE FLUXO (inicial neutro - StageResolver define o contexto)
        current_stage=ConversationStage.UNSET,
        current_step=ConversationStep.NONE,
        messages=[
            {"role": "user", "content": user_message, "timestamp": now.isoformat()}
        ]
        if user_message
        else [],
        last_user_message=user_message,
        # DADOS COLETADOS (vazio inicialmente)
        collected_data=CollectedData(),
        # SISTEMA DE VALIDAÇÃO (inicializado)
        data_validation=DataValidation(
            extraction_attempts={},
            pending_confirmations=[],
            validation_history=[],
            last_extraction_error=None,
        ),
        # MÉTRICAS (inicializadas)
        conversation_metrics=ConversationMetrics(
            failed_attempts=0,
            consecutive_confusion=0,
            same_question_count=0,
            message_count=1 if user_message else 0,
            created_at=now,
            last_successful_collection=None,
            problematic_fields=[],
        ),
        # AUDITORIA (inicializada)
        decision_trail=DecisionTrail(
            last_decisions=[], edge_function_calls=[], validation_failures=[]
        ),
        # ERROR RECOVERY (inicializado)
        error_recovery=ErrorRecoveryState(
            critical_delivery_failure=False,
            critical_error=None,
            requires_manual_intervention=False,
            delivery_failed=False,
            delivery_fallback_used=False,
            last_delivery_error=None,
            emergency_response_sent=False,
            validation_failed=False,
            validation_error=None,
            validation_failed_count=0,
            recovery_attempts=0,
            last_recovery_attempt=None,
            recovery_strategy=None,
            error_history=[],
        ),
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
    state["decision_trail"]["last_decisions"].append(
        {**decision, "timestamp": datetime.now(timezone.utc).isoformat()}
    )

    # Manter apenas últimas 10 decisões
    if len(state["decision_trail"]["last_decisions"]) > 10:
        state["decision_trail"]["last_decisions"] = state["decision_trail"][
            "last_decisions"
        ][-10:]


def add_validation_failure(state: CeciliaState, failure: Dict[str, Any]) -> None:
    """Helper para registrar falha de validação"""
    state["decision_trail"]["validation_failures"].append(
        {**failure, "timestamp": datetime.now(timezone.utc).isoformat()}
    )

    # Manter apenas últimas 5 falhas
    if len(state["decision_trail"]["validation_failures"]) > 5:
        state["decision_trail"]["validation_failures"] = state["decision_trail"][
            "validation_failures"
        ][-5:]


def add_error_to_recovery(state: CeciliaState, error: Dict[str, Any]) -> None:
    """Helper para adicionar erro ao sistema de recovery"""
    error_entry = {**error, "timestamp": datetime.now(timezone.utc).isoformat()}

    state["error_recovery"]["error_history"].append(error_entry)

    # Manter apenas últimos 10 erros
    if len(state["error_recovery"]["error_history"]) > 10:
        state["error_recovery"]["error_history"] = state["error_recovery"][
            "error_history"
        ][-10:]


def set_error_recovery_field(state: CeciliaState, field_name: str, value: Any) -> None:
    """Helper para definir campos do sistema de error recovery"""
    if field_name in state["error_recovery"]:
        state["error_recovery"][field_name] = value
    else:
        # Add to error history if field doesn't exist
        add_error_to_recovery(
            state,
            {
                "type": "unknown_error_field",
                "field_name": field_name,
                "value": str(value),
            },
        )


def increment_recovery_attempts(state: CeciliaState) -> None:
    """Helper para incrementar tentativas de recovery"""
    state["error_recovery"]["recovery_attempts"] += 1
    state["error_recovery"]["last_recovery_attempt"] = datetime.now(
        timezone.utc
    ).isoformat()


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
