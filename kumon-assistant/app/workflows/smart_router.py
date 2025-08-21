"""
Smart Routing Engine for Kumon Assistant

This module provides intelligent routing decisions based on intent classification,
context analysis, and business rules. It integrates all Phase 4 components to 
deliver sophisticated conversation flow control.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from ..core.logger import app_logger
from .states import ConversationState, WorkflowStage, ConversationStep
from .intent_classifier import (
    intent_classifier, 
    IntentResult, 
    IntentCategory, 
    IntentSubcategory
)
from .context_manager import (
    context_manager, 
    TopicTransition, 
    ConversationContextManager
)


class RoutingPriority(Enum):
    """Priority levels for routing decisions"""
    CRITICAL = "critical"      # User requests human, technical issues
    HIGH = "high"             # Direct scheduling, pricing questions
    MEDIUM = "medium"         # Information requests, clarifications
    LOW = "low"              # Small talk, general conversation


class RoutingStrategy(Enum):
    """Routing strategies based on context"""
    DIRECT = "direct"                    # Direct to specific node
    CONTEXTUAL = "contextual"           # Based on conversation context
    PROGRESSIVE = "progressive"         # Follow natural progression
    RECOVERY = "recovery"               # Recover from confusion/error
    ESCALATION = "escalation"           # Escalate to human


@dataclass
class RoutingDecision:
    """Complete routing decision with reasoning"""
    target_node: str
    target_stage: WorkflowStage
    target_step: ConversationStep
    strategy: RoutingStrategy
    priority: RoutingPriority
    confidence: float
    reasoning: str
    context_used: Dict[str, Any]
    fallback_options: List[str]
    requires_context_update: bool = True
    estimated_completion_probability: float = 0.5


@dataclass
class BusinessRule:
    """Business rule for routing decisions"""
    name: str
    condition: str
    action: str
    priority: int
    active: bool = True


class SmartConversationRouter:
    """
    Intelligent conversation router with advanced decision-making
    
    This router combines intent classification, context analysis, and business rules
    to make sophisticated routing decisions that improve conversation flow and outcomes.
    """
    
    def __init__(self):
        self.intent_classifier = intent_classifier
        self.context_manager = context_manager
        
        # Business rules for routing decisions
        self.business_rules = self._build_business_rules()
        
        # Stage progression logic
        self.stage_progressions = self._build_stage_progressions()
        
        # Routing performance tracking
        self.routing_stats = {
            "total_decisions": 0,
            "successful_routes": 0,
            "context_reversals": 0,
            "escalations": 0
        }
        
        app_logger.info("Smart Conversation Router initialized")
    
    def _build_business_rules(self) -> List[BusinessRule]:
        """Build business rules for routing decisions"""
        return [
            BusinessRule(
                name="weekend_scheduling_block",
                condition="scheduling_intent AND (saturday OR sunday)",
                action="inform_weekday_only",
                priority=10
            ),
            BusinessRule(
                name="direct_human_request",
                condition="explicit_human_request",
                action="escalate_to_human",
                priority=20
            ),
            BusinessRule(
                name="price_objection_handling",
                condition="price_objection AND information_stage",
                action="provide_value_proposition",
                priority=15
            ),
            BusinessRule(
                name="multiple_confusion_escalation",
                condition="confusion_count >= 3",
                action="escalate_to_human",
                priority=18
            ),
            BusinessRule(
                name="high_value_lead_priority",
                condition="scheduling_intent AND engagement_score > 0.8",
                action="prioritize_scheduling",
                priority=12
            ),
            BusinessRule(
                name="context_jump_recovery",
                condition="topic_jump AND previous_incomplete",
                action="acknowledge_and_continue",
                priority=8
            ),
            BusinessRule(
                name="completion_detection",
                condition="booking_confirmed OR explicit_goodbye",
                action="complete_conversation",
                priority=25
            )
        ]
    
    def _build_stage_progressions(self) -> Dict[WorkflowStage, Dict[str, Any]]:
        """Build stage progression logic"""
        return {
            WorkflowStage.GREETING: {
                "next_stages": [WorkflowStage.INFORMATION_GATHERING, WorkflowStage.SCHEDULING],
                "completion_criteria": ["name_collected", "interest_identified"],
                "bypass_conditions": ["direct_scheduling_request"],
                "typical_duration": timedelta(minutes=2)
            },
            WorkflowStage.INFORMATION_GATHERING: {
                "next_stages": [WorkflowStage.SCHEDULING, WorkflowStage.INFORMATION_GATHERING],
                "completion_criteria": ["program_explained", "pricing_discussed"],
                "bypass_conditions": ["direct_booking_request"],
                "typical_duration": timedelta(minutes=5)
            },
            WorkflowStage.SCHEDULING: {
                "next_stages": [WorkflowStage.COMPLETED],
                "completion_criteria": ["appointment_booked", "contact_collected"],
                "bypass_conditions": [],
                "typical_duration": timedelta(minutes=3)
            },
            WorkflowStage.FALLBACK: {
                "next_stages": [WorkflowStage.GREETING, WorkflowStage.INFORMATION_GATHERING, WorkflowStage.SCHEDULING],
                "completion_criteria": ["confusion_resolved"],
                "bypass_conditions": ["escalation_required"],
                "typical_duration": timedelta(minutes=1)
            }
        }
    
    async def make_routing_decision(
        self, 
        conversation_state: ConversationState
    ) -> RoutingDecision:
        """
        Make intelligent routing decision based on all available context
        
        Args:
            conversation_state: Current conversation state
            
        Returns:
            RoutingDecision: Comprehensive routing decision
        """
        try:
            self.routing_stats["total_decisions"] += 1
            
            app_logger.info(f"Making routing decision for {conversation_state['phone_number']}")
            
            # Step 1: Classify intent with context
            intent_result = await self.intent_classifier.classify_intent(
                conversation_state["user_message"], 
                conversation_state
            )
            
            # Step 2: Analyze conversation context
            topic_transition = self.context_manager.detect_topic_transition(
                conversation_state["user_message"], 
                conversation_state
            )
            
            # Step 3: Resolve references
            resolved_message, references = self.context_manager.resolve_references(
                conversation_state["user_message"], 
                conversation_state
            )
            
            # Update state with resolved message
            if resolved_message != conversation_state["user_message"]:
                conversation_state["user_message"] = resolved_message
                app_logger.info(f"Message resolved with references: {len(references)} found")
            
            # Step 4: Apply business rules
            business_decision = self._apply_business_rules(
                intent_result, 
                conversation_state, 
                topic_transition
            )
            
            if business_decision:
                app_logger.info(f"Business rule applied: {business_decision.reasoning}")
                return business_decision
            
            # Step 5: Make contextual routing decision
            routing_decision = await self._make_contextual_decision(
                intent_result,
                topic_transition,
                conversation_state,
                references
            )
            
            # Step 6: Validate and optimize decision
            optimized_decision = self._optimize_routing_decision(
                routing_decision, 
                conversation_state
            )
            
            # Step 7: Update context based on decision
            if optimized_decision.requires_context_update:
                self.context_manager.update_context_from_message(
                    conversation_state["user_message"],
                    conversation_state,
                    detected_topics=self._extract_topics_from_intent(intent_result)
                )
            
            app_logger.info(f"Routing decision: {optimized_decision.target_node} "
                          f"(confidence: {optimized_decision.confidence:.2f})")
            
            self.routing_stats["successful_routes"] += 1
            return optimized_decision
            
        except Exception as e:
            app_logger.error(f"Error in routing decision: {e}")
            # Return safe fallback decision
            return RoutingDecision(
                target_node="fallback",
                target_stage=WorkflowStage.FALLBACK,
                target_step=ConversationStep.CLARIFICATION_ATTEMPT,
                strategy=RoutingStrategy.RECOVERY,
                priority=RoutingPriority.MEDIUM,
                confidence=0.3,
                reasoning=f"Error in routing: {str(e)}",
                context_used={},
                fallback_options=["greeting", "information"]
            )
    
    def _apply_business_rules(
        self,
        intent_result: IntentResult,
        conversation_state: ConversationState,
        topic_transition: TopicTransition
    ) -> Optional[RoutingDecision]:
        """Apply business rules to determine routing"""
        try:
            # DEBUG: Check conversation_state structure
            app_logger.info(f"DEBUG: conversation_state keys: {list(conversation_state.keys())}")
            app_logger.info(f"DEBUG: metrics in state: {'metrics' in conversation_state}")
            app_logger.info(f"DEBUG: metrics type: {type(conversation_state.get('metrics'))}")
            
            # Prepare context for rule evaluation
            rule_context = self._build_rule_context(
                intent_result, conversation_state, topic_transition
            )
            
            # Apply rules in priority order
            applicable_rules = []
            for rule in sorted(self.business_rules, key=lambda r: r.priority, reverse=True):
                if not rule.active:
                    continue
                
                if self._evaluate_rule_condition(rule.condition, rule_context):
                    applicable_rules.append(rule)
            
            # Execute highest priority rule
            if applicable_rules:
                rule = applicable_rules[0]
                return self._execute_business_rule(rule, rule_context, conversation_state)
            
            return None
            
        except Exception as e:
            app_logger.error(f"Error applying business rules: {e}")
            return None
    
    def _build_rule_context(
        self,
        intent_result: IntentResult,
        conversation_state: ConversationState,
        topic_transition: TopicTransition
    ) -> Dict[str, Any]:
        """Build context for business rule evaluation"""
        from .states import ConversationMetrics
        
        user_message = conversation_state["user_message"].lower()
        metrics = conversation_state.get("metrics", ConversationMetrics())
        
        return {
            # Intent-based conditions
            "scheduling_intent": intent_result.category == IntentCategory.SCHEDULING if intent_result else False,
            "information_intent": intent_result.category == IntentCategory.INFORMATION_REQUEST if intent_result else False,
            "clarification_intent": intent_result.category == IntentCategory.CLARIFICATION if intent_result else False,
            "objection_intent": intent_result.category == IntentCategory.OBJECTION if intent_result else False,
            "decision_intent": intent_result.category == IntentCategory.DECISION if intent_result else False,
            
            # Content-based conditions
            "saturday": any(word in user_message for word in ["sábado", "saturday"]),
            "sunday": any(word in user_message for word in ["domingo", "sunday"]),
            "explicit_human_request": any(phrase in user_message for phrase in [
                "falar com pessoa", "atendente", "humano", "human"
            ]),
            "price_objection": any(word in user_message for word in ["caro", "expensive"]),
            "booking_confirmed": getattr(conversation_state.get("user_context"), "booking_id", None) is not None,
            "explicit_goodbye": any(word in user_message for word in [
                "tchau", "obrigado", "bye", "goodbye"
            ]),
            
            # State-based conditions
            "information_stage": conversation_state["stage"] == WorkflowStage.INFORMATION_GATHERING,
            "scheduling_stage": conversation_state["stage"] == WorkflowStage.SCHEDULING,
            "confusion_count": metrics.clarification_attempts,
            "topic_jump": topic_transition == TopicTransition.NEW_TOPIC if topic_transition else False,
            "previous_incomplete": metrics.consecutive_confusion > 0,
            
            # Context-based conditions
            "engagement_score": getattr(conversation_state.get("user_context"), "interest_level", 0.5),
            "direct_scheduling_request": (
                intent_result and intent_result.category == IntentCategory.SCHEDULING and
                intent_result.subcategory == IntentSubcategory.DIRECT_BOOKING
            ),
            "direct_booking_request": intent_result and intent_result.subcategory == IntentSubcategory.DIRECT_BOOKING,
            "escalation_required": conversation_state.get("requires_human", False)
        }
    
    def _evaluate_rule_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a business rule condition"""
        try:
            # Simple condition evaluation
            # Replace condition variables with context values
            for key, value in context.items():
                if isinstance(value, bool):
                    condition = condition.replace(key, str(value))
                elif isinstance(value, (int, float)):
                    condition = condition.replace(key, str(value))
            
            # Evaluate logical expressions
            condition = condition.replace("AND", "and").replace("OR", "or")
            condition = condition.replace(">=", ">=").replace("<=", "<=")
            
            # Safe evaluation (only allow specific operations)
            allowed_names = {"True", "False", "and", "or", "not"}
            if all(name in allowed_names or name.isdigit() or "." in name 
                   for name in condition.replace("(", "").replace(")", "").replace(" ", "").split()):
                return eval(condition)
            
            return False
            
        except Exception as e:
            app_logger.error(f"Error evaluating rule condition '{condition}': {e}")
            return False
    
    def _execute_business_rule(
        self,
        rule: BusinessRule,
        rule_context: Dict[str, Any],
        conversation_state: ConversationState
    ) -> RoutingDecision:
        """Execute a business rule and return routing decision"""
        action = rule.action
        
        if action == "escalate_to_human":
            return RoutingDecision(
                target_node="human_handoff",
                target_stage=WorkflowStage.COMPLETED,
                target_step=ConversationStep.CONVERSATION_ENDED,
                strategy=RoutingStrategy.ESCALATION,
                priority=RoutingPriority.CRITICAL,
                confidence=0.95,
                reasoning=f"Business rule: {rule.name}",
                context_used=rule_context,
                fallback_options=[]
            )
        
        elif action == "inform_weekday_only":
            return RoutingDecision(
                target_node="scheduling",
                target_stage=WorkflowStage.SCHEDULING,
                target_step=ConversationStep.COLLECT_PREFERENCES,
                strategy=RoutingStrategy.DIRECT,
                priority=RoutingPriority.HIGH,
                confidence=0.9,
                reasoning=f"Business rule: Weekend scheduling not available",
                context_used=rule_context,
                fallback_options=["information"]
            )
        
        elif action == "prioritize_scheduling":
            return RoutingDecision(
                target_node="scheduling",
                target_stage=WorkflowStage.SCHEDULING,
                target_step=ConversationStep.SUGGEST_APPOINTMENT,
                strategy=RoutingStrategy.DIRECT,
                priority=RoutingPriority.HIGH,
                confidence=0.9,
                reasoning=f"Business rule: High-value lead prioritization",
                context_used=rule_context,
                fallback_options=["information"]
            )
        
        elif action == "complete_conversation":
            return RoutingDecision(
                target_node="completed",
                target_stage=WorkflowStage.COMPLETED,
                target_step=ConversationStep.CONVERSATION_ENDED,
                strategy=RoutingStrategy.DIRECT,
                priority=RoutingPriority.HIGH,
                confidence=0.95,
                reasoning=f"Business rule: Conversation completion detected",
                context_used=rule_context,
                fallback_options=[]
            )
        
        elif action == "acknowledge_and_continue":
            return RoutingDecision(
                target_node=conversation_state["stage"].value,
                target_stage=conversation_state["stage"],
                target_step=conversation_state["step"],
                strategy=RoutingStrategy.CONTEXTUAL,
                priority=RoutingPriority.MEDIUM,
                confidence=0.8,
                reasoning=f"Business rule: Context jump acknowledgment",
                context_used=rule_context,
                fallback_options=["information"]
            )
        
        # Default fallback
        return RoutingDecision(
            target_node="fallback",
            target_stage=WorkflowStage.FALLBACK,
            target_step=ConversationStep.CLARIFICATION_ATTEMPT,
            strategy=RoutingStrategy.RECOVERY,
            priority=RoutingPriority.LOW,
            confidence=0.5,
            reasoning=f"Business rule executed but no specific action: {action}",
            context_used=rule_context,
            fallback_options=["greeting", "information"]
        )
    
    async def _make_contextual_decision(
        self,
        intent_result: IntentResult,
        topic_transition: TopicTransition,
        conversation_state: ConversationState,
        references: List[Any]
    ) -> RoutingDecision:
        """Make contextual routing decision based on intent and context"""
        try:
            current_stage = conversation_state["stage"]
            current_step = conversation_state["step"]
            
            # Use intent routing decision as base
            base_target = intent_result.routing_decision or current_stage.value
            
            # Adjust based on topic transition
            if topic_transition == TopicTransition.NEW_TOPIC:
                # User changed topic completely - follow their lead
                confidence_adjustment = 0.1
                strategy = RoutingStrategy.DIRECT
            elif topic_transition == TopicTransition.CONTINUATION:
                # Continuing current topic - high confidence
                confidence_adjustment = 0.2
                strategy = RoutingStrategy.PROGRESSIVE
            elif topic_transition == TopicTransition.RETURN:
                # Returning to previous topic - moderate confidence
                confidence_adjustment = 0.15
                strategy = RoutingStrategy.CONTEXTUAL
            else:
                # Elaboration or digression - moderate confidence
                confidence_adjustment = 0.1
                strategy = RoutingStrategy.CONTEXTUAL
            
            # Determine target stage and step
            target_stage, target_step = self._determine_target_stage_step(
                intent_result, current_stage, current_step
            )
            
            # Calculate confidence
            base_confidence = intent_result.confidence
            final_confidence = min(0.95, base_confidence + confidence_adjustment)
            
            # Determine priority
            priority = self._determine_priority(intent_result, conversation_state)
            
            # Build reasoning
            reasoning = f"Intent: {intent_result.category.value}"
            if intent_result.subcategory:
                reasoning += f"/{intent_result.subcategory.value}"
            reasoning += f", Transition: {topic_transition.value}"
            if references:
                reasoning += f", References resolved: {len(references)}"
            
            return RoutingDecision(
                target_node=base_target,
                target_stage=target_stage,
                target_step=target_step,
                strategy=strategy,
                priority=priority,
                confidence=final_confidence,
                reasoning=reasoning,
                context_used={
                    "intent_category": intent_result.category.value,
                    "topic_transition": topic_transition.value,
                    "references_count": len(references),
                    "current_stage": current_stage.value
                },
                fallback_options=self._get_fallback_options(target_stage)
            )
            
        except Exception as e:
            app_logger.error(f"Error in contextual decision making: {e}")
            # Return safe fallback
            return RoutingDecision(
                target_node="fallback",
                target_stage=WorkflowStage.FALLBACK,
                target_step=ConversationStep.CLARIFICATION_ATTEMPT,
                strategy=RoutingStrategy.RECOVERY,
                priority=RoutingPriority.MEDIUM,
                confidence=0.4,
                reasoning=f"Contextual decision error: {str(e)}",
                context_used={},
                fallback_options=["greeting"]
            )
    
    def _determine_target_stage_step(
        self,
        intent_result: IntentResult,
        current_stage: WorkflowStage,
        current_step: ConversationStep
    ) -> Tuple[WorkflowStage, ConversationStep]:
        """Determine target stage and step based on intent"""
        category = intent_result.category
        subcategory = intent_result.subcategory
        
        # Map intents to stages and steps
        if category == IntentCategory.GREETING:
            if subcategory == IntentSubcategory.NAME_PROVIDING:
                return WorkflowStage.GREETING, ConversationStep.COLLECT_NAME
            else:
                return WorkflowStage.GREETING, ConversationStep.WELCOME
        
        elif category == IntentCategory.INFORMATION_REQUEST:
            if subcategory in [IntentSubcategory.PROGRAM_MATHEMATICS, IntentSubcategory.PROGRAM_PORTUGUESE]:
                return WorkflowStage.INFORMATION_GATHERING, ConversationStep.PROVIDE_PROGRAM_INFO
            elif subcategory == IntentSubcategory.PRICING_GENERAL:
                return WorkflowStage.INFORMATION_GATHERING, ConversationStep.DISCUSS_PRICING
            else:
                return WorkflowStage.INFORMATION_GATHERING, ConversationStep.PROVIDE_PROGRAM_INFO
        
        elif category == IntentCategory.SCHEDULING:
            if subcategory == IntentSubcategory.DIRECT_BOOKING:
                return WorkflowStage.SCHEDULING, ConversationStep.SUGGEST_APPOINTMENT
            elif subcategory == IntentSubcategory.TIME_PREFERENCE:
                return WorkflowStage.SCHEDULING, ConversationStep.COLLECT_PREFERENCES
            else:
                return WorkflowStage.SCHEDULING, ConversationStep.SUGGEST_APPOINTMENT
        
        elif category == IntentCategory.CLARIFICATION:
            return WorkflowStage.FALLBACK, ConversationStep.CLARIFICATION_ATTEMPT
        
        elif category == IntentCategory.DECISION:
            # User made a decision - progress to next stage
            if current_stage == WorkflowStage.GREETING:
                return WorkflowStage.INFORMATION_GATHERING, ConversationStep.PROVIDE_PROGRAM_INFO
            elif current_stage == WorkflowStage.INFORMATION_GATHERING:
                return WorkflowStage.SCHEDULING, ConversationStep.SUGGEST_APPOINTMENT
            else:
                return current_stage, current_step
        
        # Default: stay in current stage
        return current_stage, current_step
    
    def _determine_priority(
        self, 
        intent_result: IntentResult, 
        conversation_state: ConversationState
    ) -> RoutingPriority:
        """Determine routing priority based on intent and context"""
        category = intent_result.category
        
        if category == IntentCategory.SCHEDULING:
            return RoutingPriority.HIGH
        elif category == IntentCategory.DECISION:
            return RoutingPriority.HIGH
        elif category == IntentCategory.OBJECTION:
            return RoutingPriority.MEDIUM
        elif category == IntentCategory.INFORMATION_REQUEST:
            return RoutingPriority.MEDIUM
        elif category == IntentCategory.CLARIFICATION:
            return RoutingPriority.MEDIUM
        else:
            return RoutingPriority.LOW
    
    def _get_fallback_options(self, target_stage: WorkflowStage) -> List[str]:
        """Get fallback routing options for a target stage"""
        fallback_map = {
            WorkflowStage.GREETING: ["information"],
            WorkflowStage.INFORMATION_GATHERING: ["greeting", "scheduling"],
            WorkflowStage.SCHEDULING: ["information"],
            WorkflowStage.FALLBACK: ["greeting", "information"],
            WorkflowStage.COMPLETED: []
        }
        
        return fallback_map.get(target_stage, ["fallback"])
    
    def _optimize_routing_decision(
        self,
        decision: RoutingDecision,
        conversation_state: ConversationState
    ) -> RoutingDecision:
        """Optimize routing decision based on conversation history and performance"""
        try:
            # Check if we're in a loop (same decision repeatedly)
            from .states import ConversationMetrics
            metrics = conversation_state.get("metrics", ConversationMetrics())
            recent_flow = metrics.stage_transitions[-3:] if hasattr(metrics, "stage_transitions") else []
            
            if len(recent_flow) >= 2 and all(stage == decision.target_stage.value for stage in recent_flow):
                # Potential loop detected - add variety
                if decision.fallback_options:
                    decision.target_node = decision.fallback_options[0]
                    decision.reasoning += " (loop prevention)"
                    decision.confidence *= 0.8
            
            # Boost confidence for successful patterns
            current_stage = conversation_state["stage"]
            if (current_stage == WorkflowStage.INFORMATION_GATHERING and 
                decision.target_stage == WorkflowStage.SCHEDULING):
                # Natural progression - boost confidence
                decision.confidence = min(0.95, decision.confidence + 0.1)
                decision.estimated_completion_probability = 0.8
            
            # Lower confidence for risky transitions
            if (current_stage == WorkflowStage.GREETING and 
                decision.target_stage == WorkflowStage.SCHEDULING):
                # Skipping information stage - might be risky
                decision.confidence *= 0.9
                decision.estimated_completion_probability = 0.6
            
            return decision
            
        except Exception as e:
            app_logger.error(f"Error optimizing routing decision: {e}")
            return decision
    
    def _extract_topics_from_intent(self, intent_result: IntentResult) -> List[str]:
        """Extract topics from intent result for context updates"""
        topics = []
        
        if intent_result.category == IntentCategory.INFORMATION_REQUEST:
            if intent_result.subcategory == IntentSubcategory.PROGRAM_MATHEMATICS:
                topics.append("mathematics")
            elif intent_result.subcategory == IntentSubcategory.PROGRAM_PORTUGUESE:
                topics.append("portuguese")
            elif intent_result.subcategory == IntentSubcategory.PRICING_GENERAL:
                topics.append("pricing")
            elif intent_result.subcategory == IntentSubcategory.METHODOLOGY_GENERAL:
                topics.append("methodology")
        
        elif intent_result.category == IntentCategory.SCHEDULING:
            topics.append("scheduling")
        
        return topics
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing performance statistics"""
        success_rate = (self.routing_stats["successful_routes"] / 
                       max(1, self.routing_stats["total_decisions"]))
        
        return {
            **self.routing_stats,
            "success_rate": success_rate,
            "active_business_rules": len([r for r in self.business_rules if r.active]),
            "total_business_rules": len(self.business_rules)
        }


# Global instance
smart_router = SmartConversationRouter()