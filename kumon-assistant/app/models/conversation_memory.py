"""
Advanced Conversation Memory Models with ML/BI Optimization

This module defines the conversation memory architecture using Redis for fast access
and PostgreSQL for persistent storage, following 2024 best practices for ML pipelines.

Architecture Design Principles:
1. Time-series optimization for conversation analytics
2. Denormalized storage for fast ML feature extraction  
3. Event-driven architecture for real-time insights
4. Schema versioning for model evolution
5. JSONB fields for flexible metadata evolution
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field, validator
import json

# ============================================================================
# ENUMS FOR CATEGORICAL DATA (OPTIMIZED FOR ML FEATURE ENCODING)
# ============================================================================

class ConversationStage(str, Enum):
    """Conversation stages - ordered by typical flow for ML sequence modeling"""
    GREETING = "greeting"
    QUALIFICATION = "qualification" 
    INFORMATION_GATHERING = "information_gathering"
    SCHEDULING = "scheduling"
    CONFIRMATION = "confirmation"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    HUMAN_ESCALATION = "human_escalation"

class ConversationStep(str, Enum):
    """Granular conversation steps for detailed flow analysis"""
    # Greeting steps
    WELCOME = "welcome"
    PARENT_NAME_COLLECTION = "parent_name_collection"
    INITIAL_RESPONSE = "initial_response"
    
    # Qualification steps  
    CHILD_NAME_COLLECTION = "child_name_collection"
    CHILD_AGE_COLLECTION = "child_age_collection"
    PROGRAM_INTEREST_DETECTION = "program_interest_detection"
    
    # Information gathering steps
    PROGRAM_EXPLANATION = "program_explanation"
    PRICING_DISCUSSION = "pricing_discussion"
    SCHEDULE_EXPLANATION = "schedule_explanation"
    
    # Scheduling steps
    AVAILABILITY_COLLECTION = "availability_collection"
    SLOT_PRESENTATION = "slot_presentation"
    EMAIL_COLLECTION = "email_collection"
    APPOINTMENT_CREATION = "appointment_creation"
    
    # Confirmation steps
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    FOLLOW_UP_SCHEDULING = "follow_up_scheduling"
    
    # Terminal steps
    CONVERSATION_ENDED = "conversation_ended"
    HUMAN_HANDOFF = "human_handoff"

class UserIntent(str, Enum):
    """User intent classification for ML training data"""
    GREETING = "greeting"
    INFORMATION_REQUEST = "information_request"
    BOOKING_REQUEST = "booking_request"
    PRICING_INQUIRY = "pricing_inquiry"
    SCHEDULE_INQUIRY = "schedule_inquiry"
    PROGRAM_INQUIRY = "program_inquiry"
    COMPLAINT = "complaint"
    CONFUSION = "confusion"
    AFFIRMATION = "affirmation"
    NEGATION = "negation"
    HUMAN_REQUEST = "human_request"
    GOODBYE = "goodbye"
    OTHER = "other"

class SentimentLabel(str, Enum):
    """Sentiment analysis labels for conversation quality tracking"""
    VERY_POSITIVE = "very_positive"  # 0.8-1.0
    POSITIVE = "positive"            # 0.4-0.8  
    NEUTRAL = "neutral"              # -0.4-0.4
    NEGATIVE = "negative"            # -0.8--0.4
    VERY_NEGATIVE = "very_negative"  # -1.0--0.8

class ConversationStatus(str, Enum):
    """Overall conversation lifecycle status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ESCALATED = "escalated"

class LeadScore(str, Enum):
    """Lead scoring categories for sales analytics"""
    HOT = "hot"          # 80-100: Ready to book
    WARM = "warm"        # 60-79: High interest, needs nurturing
    COLD = "cold"        # 40-59: Some interest, long-term nurturing
    QUALIFIED = "qualified"  # 20-39: Qualified but low engagement
    UNQUALIFIED = "unqualified"  # 0-19: Not a good fit

# ============================================================================
# ML-OPTIMIZED DATA MODELS
# ============================================================================

@dataclass
class ConversationMetrics:
    """Real-time conversation metrics for ML feature engineering"""
    
    # Engagement metrics
    message_count: int = 0
    avg_response_time_seconds: float = 0.0
    user_message_length_avg: float = 0.0
    bot_message_length_avg: float = 0.0
    
    # Quality metrics  
    failed_attempts: int = 0
    consecutive_confusion: int = 0
    clarification_requests: int = 0
    sentiment_score_avg: float = 0.0
    satisfaction_score: float = 0.0
    
    # Behavioral metrics
    topic_switches: int = 0
    repetition_count: int = 0
    stage_progression_time: Dict[str, float] = field(default_factory=dict)
    
    # Business metrics
    lead_score: int = 0
    conversion_probability: float = 0.0
    estimated_value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class UserProfile:
    """Persistent user profile for personalization and analytics"""
    
    # Identity
    user_id: str
    phone_number: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_interaction: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Personal information
    parent_name: Optional[str] = None
    preferred_name: Optional[str] = None  
    child_name: Optional[str] = None
    child_age: Optional[int] = None
    
    # Preferences and interests
    program_interests: List[str] = field(default_factory=list)
    availability_preferences: Dict[str, Any] = field(default_factory=dict)
    communication_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # Historical metrics (aggregated)
    total_interactions: int = 0
    total_messages: int = 0
    avg_session_duration: float = 0.0
    conversion_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # ML features (computed)
    engagement_score: float = 0.0
    churn_probability: float = 0.0
    lifetime_value_prediction: float = 0.0
    persona_cluster: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['last_interaction'] = self.last_interaction.isoformat()
        return data

@dataclass
class ConversationMessage:
    """Individual message with ML-ready features"""
    
    # Identity (required fields first)
    message_id: str
    conversation_id: str
    user_id: str
    timestamp: datetime
    
    # Content (required fields)
    content: str
    is_from_user: bool
    conversation_stage: ConversationStage
    conversation_step: ConversationStep
    
    # Optional content fields
    message_type: str = "text"  # text, image, button, etc.
    
    # AI-generated features
    intent: Optional[UserIntent] = None
    intent_confidence: float = 0.0
    sentiment: Optional[SentimentLabel] = None  
    sentiment_score: float = 0.0
    entities: List[Dict[str, Any]] = field(default_factory=list)
    response_time_seconds: Optional[float] = None
    message_length: int = 0
    
    # Metadata for ML
    features: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        self.message_length = len(self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class ConversationSession:
    """Main conversation session model optimized for analytics"""
    
    # Primary identifiers (required fields first)
    session_id: str
    user_id: str
    phone_number: str
    user_profile: UserProfile
    
    # Timestamps (critical for time-series analysis)
    created_at: datetime
    updated_at: datetime
    last_activity: datetime
    
    # Optional timestamps
    ended_at: Optional[datetime] = None
    
    # Current state (with defaults)
    status: ConversationStatus = ConversationStatus.ACTIVE
    current_stage: ConversationStage = ConversationStage.GREETING
    current_step: ConversationStep = ConversationStep.WELCOME
    
    # Conversation data
    messages: List[ConversationMessage] = field(default_factory=list)
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Real-time metrics
    metrics: ConversationMetrics = field(default_factory=ConversationMetrics)
    
    # Business context
    lead_score_category: LeadScore = LeadScore.UNQUALIFIED
    conversion_events: List[Dict[str, Any]] = field(default_factory=list)
    scheduling_context: Dict[str, Any] = field(default_factory=dict)
    
    # ML/BI metadata
    session_features: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, Any] = field(default_factory=dict)  # For supervised learning
    predictions: Dict[str, Any] = field(default_factory=dict)  # Model outputs
    
    # Schema versioning for model evolution
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        if not self.user_id:
            self.user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    def add_message(self, message: ConversationMessage):
        """Add message and update metrics"""
        self.messages.append(message)
        self.metrics.message_count += 1
        self.last_activity = message.timestamp
        self.updated_at = datetime.now(timezone.utc)
        
        # Update average message lengths
        user_messages = [m for m in self.messages if m.is_from_user]
        bot_messages = [m for m in self.messages if not m.is_from_user]
        
        if user_messages:
            self.metrics.user_message_length_avg = sum(m.message_length for m in user_messages) / len(user_messages)
        if bot_messages:
            self.metrics.bot_message_length_avg = sum(m.message_length for m in bot_messages) / len(bot_messages)
    
    def update_stage(self, new_stage: ConversationStage, new_step: ConversationStep):
        """Update conversation stage and track progression"""
        old_stage = self.current_stage
        old_step = self.current_step
        
        self.current_stage = new_stage
        self.current_step = new_step
        self.updated_at = datetime.now(timezone.utc)
        
        # Track stage history for analytics
        stage_change = {
            "timestamp": self.updated_at.isoformat(),
            "from_stage": old_stage.value,
            "to_stage": new_stage.value,
            "from_step": old_step.value,
            "to_step": new_step.value,
            "duration_seconds": (self.updated_at - self.last_activity).total_seconds()
        }
        self.stage_history.append(stage_change)
        
        # Update stage progression metrics
        stage_key = f"{old_stage.value}_to_{new_stage.value}"
        if stage_key not in self.metrics.stage_progression_time:
            self.metrics.stage_progression_time[stage_key] = 0.0
        self.metrics.stage_progression_time[stage_key] += stage_change["duration_seconds"]
    
    def calculate_session_duration(self) -> float:
        """Calculate total session duration in seconds"""
        end_time = self.ended_at or self.last_activity
        return (end_time - self.created_at).total_seconds()
    
    def get_ml_features(self) -> Dict[str, Any]:
        """Extract ML features for model training/prediction"""
        duration = self.calculate_session_duration()
        
        features = {
            # Temporal features
            "session_duration_seconds": duration,
            "hour_of_day": self.created_at.hour,
            "day_of_week": self.created_at.weekday(),
            "days_since_first_contact": 0,  # To be calculated from user profile
            
            # Engagement features
            "message_count": self.metrics.message_count,
            "avg_response_time": self.metrics.avg_response_time_seconds,
            "user_message_length_avg": self.metrics.user_message_length_avg,
            "bot_message_length_avg": self.metrics.bot_message_length_avg,
            
            # Quality features
            "failed_attempts": self.metrics.failed_attempts,
            "consecutive_confusion": self.metrics.consecutive_confusion,
            "clarification_requests": self.metrics.clarification_requests,
            "sentiment_score_avg": self.metrics.sentiment_score_avg,
            
            # Behavioral features  
            "topic_switches": self.metrics.topic_switches,
            "repetition_count": self.metrics.repetition_count,
            "stage_changes": len(self.stage_history),
            
            # Business features
            "lead_score": self.metrics.lead_score,
            "reached_scheduling": self.current_stage.value in ["scheduling", "confirmation", "completed"],
            "completed_booking": any(event.get("type") == "booking_completed" for event in self.conversion_events),
            
            # User context features
            "has_child_info": bool(self.user_profile.child_name and self.user_profile.child_age),
            "program_interests_count": len(self.user_profile.program_interests),
            "repeat_user": self.user_profile.total_interactions > 1,
        }
        
        # Add categorical encodings
        features.update({
            f"stage_{stage.value}": (self.current_stage == stage) for stage in ConversationStage
        })
        
        features.update({
            f"status_{status.value}": (self.status == status) for status in ConversationStatus  
        })
        
        return features
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        
        # Convert datetime objects
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat() 
        data['last_activity'] = self.last_activity.isoformat()
        if self.ended_at:
            data['ended_at'] = self.ended_at.isoformat()
            
        return data
    
    def to_workflow_state(self):
        """Convert ConversationSession to WorkflowState for integration"""
        from ..services.workflow_state_repository import WorkflowState
        
        # Convert messages to conversation history format
        conversation_history = []
        for message in self.messages:
            conversation_history.append({
                "role": "user" if message.is_from_user else "assistant",
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
                "message_type": message.message_type
            })
        
        # Map conversation stages to workflow stages
        stage_mapping = {
            ConversationStage.GREETING.value: "greeting",
            ConversationStage.QUALIFICATION.value: "qualification",
            ConversationStage.INFORMATION_GATHERING.value: "information_gathering", 
            ConversationStage.SCHEDULING.value: "scheduling",
            ConversationStage.CONFIRMATION.value: "confirmation",
            ConversationStage.FOLLOW_UP.value: "follow_up",
            ConversationStage.COMPLETED.value: "completed",
            ConversationStage.ABANDONED.value: "abandoned"
        }
        
        # Map conversation steps to workflow steps
        step_mapping = {
            ConversationStep.WELCOME.value: "welcome",
            ConversationStep.PARENT_NAME_COLLECTION.value: "parent_name_collection",
            ConversationStep.INITIAL_RESPONSE.value: "initial_response",
            ConversationStep.CHILD_NAME_COLLECTION.value: "child_name_collection",
            ConversationStep.CHILD_AGE_COLLECTION.value: "child_age_collection",
            ConversationStep.PROGRAM_INTEREST_DETECTION.value: "program_interest_detection"
        }
        
        # Extract user profile data
        user_profile = {}
        if hasattr(self.user_profile, 'user_name') and self.user_profile.user_name:
            user_profile['user_name'] = self.user_profile.user_name
        if hasattr(self.user_profile, 'child_name') and self.user_profile.child_name:
            user_profile['child_name'] = self.user_profile.child_name
        if hasattr(self.user_profile, 'child_age') and self.user_profile.child_age:
            user_profile['child_age'] = self.user_profile.child_age
        if hasattr(self.user_profile, 'interests') and self.user_profile.interests:
            user_profile['interests'] = self.user_profile.interests
            
        return WorkflowState(
            id=self.session_id,
            phone_number=self.phone_number,
            thread_id=f"thread_{self.phone_number}",
            current_stage=stage_mapping.get(self.current_stage.value, "greeting"),
            current_step=step_mapping.get(self.current_step.value, "welcome"),
            state_data={
                "phone_number": self.phone_number,
                "session_id": self.session_id,
                "status": self.status.value,
                "lead_score": self.lead_score_category.value,
                "scheduling_context": self.scheduling_context,
                "metrics": asdict(self.metrics)
            },
            conversation_history=conversation_history,
            user_profile=user_profile,
            detected_intent=None,  # Could be mapped from latest message intent
            scheduling_data=self.scheduling_context,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_activity=self.last_activity
        )

# ============================================================================
# PYDANTIC MODELS FOR API VALIDATION
# ============================================================================

class ConversationSessionCreate(BaseModel):
    """Pydantic model for creating new conversation session"""
    phone_number: str = Field(..., pattern=r'^\d{10,15}$')
    user_name: Optional[str] = None
    initial_message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "5511999999999",
                "user_name": "João Silva",
                "initial_message": "Olá"
            }
        }

class ConversationMessageCreate(BaseModel):
    """Pydantic model for adding messages to conversation"""
    content: str = Field(..., min_length=1, max_length=4000)
    is_from_user: bool = True
    message_type: str = "text"
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Gostaria de saber mais sobre o método Kumon",
                "is_from_user": True,
                "message_type": "text"
            }
        }

class ConversationAnalytics(BaseModel):
    """Analytics data for BI dashboards"""
    session_id: str
    user_id: str
    phone_number: str
    
    # Key metrics
    duration_seconds: float
    message_count: int
    conversion_score: float
    satisfaction_score: float
    
    # Categorical data
    final_stage: ConversationStage
    final_status: ConversationStatus
    lead_score_category: LeadScore
    
    # Timestamps
    created_at: datetime
    ended_at: Optional[datetime]
    
    # ML features (flattened for easy BI consumption)
    ml_features: Dict[str, Union[int, float, bool, str]]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_user_profile(phone_number: str, name: Optional[str] = None) -> UserProfile:
    """Create a new user profile with default values"""
    now = datetime.now(timezone.utc)
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    
    return UserProfile(
        user_id=user_id,
        phone_number=phone_number,
        created_at=now,
        updated_at=now,
        last_interaction=now,
        parent_name=name
    )

def create_conversation_session(phone_number: str, user_profile: Optional[UserProfile] = None) -> ConversationSession:
    """Create a new conversation session"""
    now = datetime.now(timezone.utc)
    session_id = f"conv_{uuid.uuid4().hex[:16]}"
    
    if user_profile is None:
        user_profile = create_user_profile(phone_number)
    
    return ConversationSession(
        session_id=session_id,
        user_id=user_profile.user_id,
        phone_number=phone_number,
        created_at=now,
        updated_at=now,
        last_activity=now,
        user_profile=user_profile
    )

def extract_ml_labels(session: ConversationSession) -> Dict[str, Any]:
    """Extract ground truth labels for supervised learning"""
    return {
        "converted": any(event.get("type") == "booking_completed" for event in session.conversion_events),
        "abandoned": session.status == ConversationStatus.ABANDONED,
        "escalated": session.status == ConversationStatus.ESCALATED,
        "satisfaction_high": session.metrics.satisfaction_score >= 0.7,
        "engagement_high": session.metrics.message_count >= 10,
        "lead_quality": session.lead_score_category.value,
        "final_stage": session.current_stage.value,
        "session_success": session.status == ConversationStatus.COMPLETED
    }