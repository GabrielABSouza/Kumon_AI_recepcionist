"""
Routing Contracts - Data structures for modular orchestration

Defines all contracts for the new modular architecture:
MessagePreprocessor → SmartRouter → ThresholdEngine → CeciliaWorkflow

Based on orchestration_flow.md specifications.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Literal, List, Mapping
import json
from ..core.state.models import ConversationStage

# ========== OUTBOX CONSTANTS ==========

OUTBOX_KEY = "outbox"  # Canonical key for outbox in state


# ========== DELIVERY CONTRACTS ==========

@dataclass
class MessageEnvelope:
    """Standard message envelope for outbox pattern"""
    text: str
    channel: Literal["web","app","whatsapp"] = "whatsapp"
    meta: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    
    def __post_init__(self):
        """Generate idempotency key if not provided"""
        if not self.idempotency_key and self.text:
            # Generate idempotency key from content hash
            import hashlib
            base = f'{self.text}|{self.channel}|{str(self.meta)}'
            self.idempotency_key = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
        
        # Validate text is not empty and doesn't contain template placeholders
        if not self.text or not self.text.strip():
            raise ValueError("MessageEnvelope text cannot be empty")
        
        if "{{" in self.text and "}}" in self.text:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"MessageEnvelope contains unresolved template: {self.text[:50]}...")
            # Don't raise - normalize instead
            self.text = self.text.replace("{{", "").replace("}}", "")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for outbox storage"""
        return {
            "text": self.text,
            "channel": self.channel,
            "meta": dict(self.meta),
            "idempotency_key": self.idempotency_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEnvelope":
        """Deserialize from dict with validation"""
        if not data.get("text"):
            raise ValueError("Invalid MessageEnvelope: text is required")
            
        return cls(
            text=data["text"],
            channel=data.get("channel", "whatsapp"), 
            meta=data.get("meta", {}),
            idempotency_key=data.get("idempotency_key", "")
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "MessageEnvelope":
        """Deserialize from JSON string"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class DeliveryPayload:
    """Payload for message delivery to channels"""
    channel: Literal["web", "app", "whatsapp"]
    content: Dict[str, Any]  # texto+rich, já adaptado por canal
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class DeliveryResult:
    """Result from message delivery attempt"""
    success: bool
    channel: str
    message_id: Optional[str] = None
    status: Literal["ok", "degraded", "failed"] = "failed"
    reason: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeliveryResult":
        """Convert dict to DeliveryResult dataclass"""
        return cls(
            success=data.get("success", False),
            channel=data.get("channel", "unknown"),
            message_id=data.get("message_id"),
            status=data.get("status", "failed"),
            reason=data.get("reason")
        )


# ========== INTENT CLASSIFICATION ==========

@dataclass
class IntentResult:
    """Result from IntentClassifier analysis with delivery integration"""
    category: str                                    # "greeting", "information", "scheduling", etc.
    subcategory: Optional[str] = None               # "appointment", "method_inquiry", etc.
    confidence: float = 0.0                         # [0,1] - confidence in classification
    context_entities: Dict[str, Any] = field(default_factory=dict)  # Extracted entities
    delivery_payload: Optional[Dict[str, Any]] = None  # Payload ready for delivery (normalized as dict)
    policy_action: Optional[str] = None             # "clarify_multi_intent", etc.
    slots: Dict[str, Any] = field(default_factory=dict)  # Extracted slots
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentResult":
        """Convert dict to IntentResult dataclass"""
        return cls(
            category=data.get("category", ""),
            subcategory=data.get("subcategory"),
            confidence=data.get("confidence", 0.0),
            context_entities=data.get("context_entities", {}),
            delivery_payload=data.get("delivery_payload"),
            policy_action=data.get("policy_action"),
            slots=data.get("slots", {})
        )


# ========== PATTERN SCORING ==========

@dataclass
class PatternScores:
    """Result from PatternScorer stage-aware analysis"""
    per_route: Dict[str, float] = field(default_factory=dict)  # {"greeting": 0.8, "scheduling": 0.2}
    best_route: str = ""                            # Route with highest score
    pattern_confidence: float = 0.0                # [0,1] - max(per_route.values())
    stage_multipliers_applied: Dict[str, float] = field(default_factory=dict)  # Applied multipliers


# ========== THRESHOLD ENGINE ==========

@dataclass
class ThresholdDecision:
    """Decision from ThresholdEngine combining all factors"""
    action: Literal[
        "proceed", 
        "enhance_with_llm", 
        "fallback_level1", 
        "fallback_level2", 
        "escalate_human"
    ]
    target_node: str                               # "greeting"|"qualification"|"information"|"scheduling"|"confirmation"|"handoff"|"completed"|"fallback"
    final_confidence: float                        # [0,1] - combined confidence after all factors
    rule_applied: str                             # Name of the rule that triggered this decision
    reasoning: str                                # Human-readable explanation
    
    # Diagnostic info
    intent_confidence: float = 0.0                # Original intent confidence
    pattern_confidence: float = 0.0              # Original pattern confidence
    stage_override: bool = False                  # True if stage logic overrode confidence
    mandatory_data_override: bool = False         # True if missing data forced decision


# ========== ROUTING DECISION ==========

@dataclass 
class RoutingDecision:
    """Final decision from SmartRouter to CeciliaWorkflow"""
    target_node: str                              # Next LangGraph node to execute
    threshold_action: str                         # Action recommended by threshold
    final_confidence: float                       # [0,1] - final decision confidence
    
    # Source confidences (for diagnostics)
    intent_confidence: float
    pattern_confidence: float
    
    # Decision metadata
    rule_applied: str                             # Which threshold rule was applied
    reasoning: str                                # Human-readable decision rationale  
    timestamp: datetime                           # When decision was made
    
    # Overrides and flags
    mandatory_data_override: bool = False         # True if forced by missing data
    stage_progression_blocked: bool = False       # True if stage transition was blocked

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingDecision":
        """Convert dict to RoutingDecision dataclass"""
        return cls(
            target_node=data.get("target_node", ""),
            threshold_action=data.get("threshold_action", ""),
            final_confidence=data.get("final_confidence", 0.0),
            intent_confidence=data.get("intent_confidence", 0.0),
            pattern_confidence=data.get("pattern_confidence", 0.0),
            rule_applied=data.get("rule_applied", ""),
            reasoning=data.get("reasoning", ""),
            timestamp=data.get("timestamp", datetime.now()),
            mandatory_data_override=data.get("mandatory_data_override", False),
            stage_progression_blocked=data.get("stage_progression_blocked", False)
        )


# ========== PREREQUISITES CONFIGURATION ==========

# Priority 1: Mandatory data collection overrides ANY confidence score
STAGE_PREREQUISITES: Dict[str, Dict[str, Any]] = {
    "scheduling": {
        "required_fields": ["parent_name", "child_name", "student_age"],
        "fallback_stage": ConversationStage.GREETING,
        "priority": 1.0,  # Maximum priority - overrides everything
    },
    "information": {
        "required_fields": ["parent_name"],
        "fallback_stage": ConversationStage.GREETING, 
        "priority": 1.0,
    },
    "confirmation": {
        "required_fields": ["contact_email", "selected_slot"],
        "fallback_stage": ConversationStage.SCHEDULING,
        "priority": 1.0,
    }
}

# Stage multipliers for pattern confidence (when no mandatory overrides)
STAGE_CONFIDENCE_MULTIPLIERS: Dict[ConversationStage, float] = {
    ConversationStage.GREETING: 1.2,              # Boost greeting detection in early conversation
    ConversationStage.QUALIFICATION: 1.1,
    ConversationStage.INFORMATION_GATHERING: 0.9, # Slightly reduce to encourage progression
    ConversationStage.SCHEDULING: 1.0,            # Neutral 
    ConversationStage.CONFIRMATION: 1.0,
    ConversationStage.COMPLETED: 0.5,             # Heavy penalty - conversation should end
}

# Confidence model weights
CONFIDENCE_WEIGHTS = {
    "intent": 0.6,     # 60% weight on intent classification
    "pattern": 0.4,    # 40% weight on pattern matching
}


# ========== UTILITY FUNCTIONS ==========

def check_mandatory_data_requirements(
    target_stage: ConversationStage, 
    collected_data: Dict[str, Any]
) -> tuple[bool, List[str]]:
    """
    Check if mandatory data requirements are met for target stage
    
    Returns:
        (requirements_met, missing_fields)
    """
    stage_key = target_stage.value
    requirements = STAGE_PREREQUISITES.get(stage_key, {})
    required_fields = requirements.get("required_fields", [])
    
    missing_fields = [
        field for field in required_fields 
        if not collected_data.get(field)
    ]
    
    return len(missing_fields) == 0, missing_fields


def get_fallback_stage_for_missing_data(target_stage: ConversationStage) -> ConversationStage:
    """Get the appropriate stage to collect missing data"""
    stage_key = target_stage.value
    requirements = STAGE_PREREQUISITES.get(stage_key, {})
    return requirements.get("fallback_stage", ConversationStage.GREETING)


# ========== STAGE/STEP SERIALIZATION ==========

def serialize_stage_step(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize stage/step Enums to strings for persistence
    
    Args:
        state_dict: State dictionary (not mutated)
        
    Returns:
        New dictionary with stage/step as strings (Enum.value)
    """
    from ..core.state.models import ConversationStage, ConversationStep
    
    # Create copy to avoid mutation
    serialized = state_dict.copy()
    
    # Serialize current_stage
    if "current_stage" in serialized:
        stage = serialized["current_stage"]
        if isinstance(stage, ConversationStage):
            serialized["current_stage"] = stage.value
        elif hasattr(stage, 'value'):  # Any Enum
            serialized["current_stage"] = stage.value
    
    # Serialize current_step
    if "current_step" in serialized:
        step = serialized["current_step"]
        if isinstance(step, ConversationStep):
            serialized["current_step"] = step.value
        elif hasattr(step, 'value'):  # Any Enum
            serialized["current_step"] = step.value
    
    return serialized


def deserialize_stage_step(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize stage/step strings to Enums for runtime usage
    
    Args:
        state_dict: State dictionary from persistence (not mutated)
        
    Returns:
        New dictionary with stage/step as Enum instances
    """
    from ..core.state.models import ConversationStage, ConversationStep
    
    # Create copy to avoid mutation
    deserialized = state_dict.copy()
    
    # Deserialize current_stage
    if "current_stage" in deserialized:
        stage = deserialized["current_stage"]
        if isinstance(stage, str):
            try:
                deserialized["current_stage"] = ConversationStage(stage)
            except ValueError:
                # Fallback for invalid stage values
                deserialized["current_stage"] = ConversationStage.GREETING
        # If already Enum, keep as-is
    
    # Deserialize current_step
    if "current_step" in deserialized:
        step = deserialized["current_step"]
        if isinstance(step, str):
            try:
                deserialized["current_step"] = ConversationStep(step)
            except ValueError:
                # Fallback for invalid step values
                deserialized["current_step"] = ConversationStep.WELCOME
        # If already Enum, keep as-is
    
    return deserialized


# ========== TYPE NORMALIZERS ==========

def normalize_routing_decision(data: Dict[str, Any] | RoutingDecision) -> RoutingDecision:
    """Normalize routing decision to dataclass"""
    if isinstance(data, RoutingDecision):
        return data
    return RoutingDecision.from_dict(data)


def normalize_intent_result(data: Dict[str, Any] | IntentResult) -> IntentResult:
    """Normalize intent result to dataclass"""  
    if isinstance(data, IntentResult):
        return data
    return IntentResult.from_dict(data)


def normalize_delivery_result(data: Dict[str, Any] | DeliveryResult) -> DeliveryResult:
    """Normalize delivery result to dataclass"""
    if isinstance(data, DeliveryResult):
        return data
    return DeliveryResult.from_dict(data)


def safe_get_delivery_field(result: DeliveryResult | Dict[str, Any], field_name: str, default=None):
    """Safely get field from DeliveryResult object or dict"""
    if isinstance(result, DeliveryResult):
        return getattr(result, field_name, default)
    elif isinstance(result, dict):
        return result.get(field_name, default)
    else:
        return default


def safe_get_payload(intent_result: IntentResult | Dict[str, Any]) -> Dict[str, Any]:
    """Safely extract delivery_payload from IntentResult (dict or dataclass)"""
    if isinstance(intent_result, dict):
        return intent_result.get("delivery_payload", {})
    else:
        return getattr(intent_result, "delivery_payload", {}) or {}


# ========== OUTBOX UTILITY FUNCTIONS ==========

def normalize_outbox_messages(obj) -> List[MessageEnvelope]:
    """
    Normalize mixed message formats to MessageEnvelope list
    
    Args:
        obj: MessageEnvelope, dict, or list of mixed types
        
    Returns:
        List[MessageEnvelope]: Validated message envelopes
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not obj:
        return []
    
    # Single message
    if isinstance(obj, MessageEnvelope):
        return [obj]
    elif isinstance(obj, dict):
        try:
            return [MessageEnvelope.from_dict(obj)]
        except ValueError as e:
            logger.warning(f"Invalid message dict ignored: {e}")
            return []
    
    # List of messages
    elif isinstance(obj, list):
        envelopes = []
        for item in obj:
            try:
                if isinstance(item, MessageEnvelope):
                    envelopes.append(item)
                elif isinstance(item, dict):
                    envelopes.append(MessageEnvelope.from_dict(item))
                else:
                    logger.warning(f"Unknown message type ignored: {type(item)}")
            except ValueError as e:
                logger.warning(f"Invalid message ignored: {e}")
        return envelopes
    
    else:
        logger.warning(f"Unknown outbox object type: {type(obj)}")
        return []


def ensure_outbox(state: Dict[str, Any]) -> list:
    """
    Ensure state[OUTBOX_KEY] exists and is a list - returns same reference
    
    CRITICAL: Always returns the same list object for reference consistency
    across Planner → Delivery hand-off. Never creates new instances.
    
    Args:
        state: Conversation state (mutated in-place)
        
    Returns:
        list: The same list reference that exists in state[OUTBOX_KEY]
    """
    if OUTBOX_KEY not in state:
        state[OUTBOX_KEY] = []
    elif not isinstance(state[OUTBOX_KEY], list):
        # Force replace with empty list if wrong type
        state[OUTBOX_KEY] = []
    
    # Always return the exact same list reference from state
    return state[OUTBOX_KEY]