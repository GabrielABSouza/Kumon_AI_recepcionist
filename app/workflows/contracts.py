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


# ========== DELIVERY CONTRACTS ==========

@dataclass
class MessageEnvelope:
    """Standard message envelope for outbox pattern"""
    text: str
    channel: Literal["web","app","whatsapp"]   # canais reais  
    meta: Mapping[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for outbox storage"""
        return {
            "text": self.text,
            "channel": self.channel,
            "meta": dict(self.meta)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEnvelope":
        """Deserialize from dict"""
        return cls(
            text=data["text"],
            channel=data["channel"], 
            meta=data.get("meta", {})
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