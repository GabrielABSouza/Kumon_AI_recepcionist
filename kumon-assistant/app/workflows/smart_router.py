"""
Smart Routing Engine for Kumon Assistant

This module provides intelligent routing decisions based on intent classification,
context analysis, and business rules. It integrates all Phase 4 components to
deliver sophisticated conversation flow control.
"""

from datetime import datetime
from typing import Any, Dict

# intent_classifier moved to SmartRouterAdapter
from ..core.logger import app_logger
from .intent_classifier import IntentCategory, IntentSubcategory
from ..core.state.models import ConversationStage, CeciliaState as ConversationState
from .contracts import IntentResult, RoutingDecision


# All routing logic moved to ThresholdSystem


class SmartConversationRouter:
    """
    Simplified routing orchestrator for Kumon Assistant
    
    Responsibilities:
    1. Collect intent classification data
    2. Send data to ThresholdSystem for processing 
    3. Convert ThresholdSystem decision to RoutingDecision
    
    All routing logic, business rules, and context processing moved to ThresholdSystem.
    """

    def __init__(self):
        # Routing performance tracking
        self.routing_stats = {
            "total_decisions": 0,
            "successful_routes": 0,
        }

        app_logger.info("Smart Conversation Router initialized (simplified)")

    def _get_stage_value(self, stage):
        """Safely extract value from stage (handle both Enum and string)"""
        if hasattr(stage, 'value'):
            return stage.value
        return str(stage) if stage else "unknown"
    
    def _get_enum_value(self, enum_obj):
        """Safely extract value from enum (handle both Enum and string)"""
        if hasattr(enum_obj, 'value'):
            return enum_obj.value
        return str(enum_obj) if enum_obj else "unknown"


    async def make_routing_decision(self, state: ConversationState, intent_result: IntentResult) -> RoutingDecision:
        """
        Simplified routing orchestrator: collect data → send to ThresholdSystem → return decision
        
        SmartRouter responsibility:
        1. Receive classified data from SmartRouterAdapter
        2. Send data to ThresholdSystem
        3. Return ThresholdSystem decision as RoutingDecision

        Args:
            state: Current conversation state
            intent_result: Already classified intent from SmartRouterAdapter

        Returns:
            RoutingDecision: Decision from ThresholdSystem
        """
        try:
            self.routing_stats["total_decisions"] += 1

            # Structured telemetry for routing start
            app_logger.info(
                f"[SMART_ROUTER] Starting routing decision",
                extra={
                    "component": "smart_router",
                    "operation": "make_routing_decision",
                    "phone_number": state.get("phone_number", "unknown")[-4:],
                    "current_stage": self._get_stage_value(state.get("current_stage", ConversationStage.GREETING)),
                    "intent_category": self._get_enum_value(intent_result.category),
                    "intent_confidence": intent_result.confidence
                }
            )

            # Intent already classified by SmartRouterAdapter

            # Step 2: Send all data to ThresholdSystem for processing and decision
            from .intelligent_threshold_system import intelligent_threshold_system
            
            threshold_decision = await intelligent_threshold_system.decide(
                intent_confidence=intent_result.confidence,
                pattern_confidence=intent_result.confidence,  # Use same confidence for now
                current_stage=state.get("current_stage", ConversationStage.GREETING),
                collected_data=state.get("collected_data", {}),
                target_intent=self._get_enum_value(intent_result.category)
            )

            # Step 3: Convert ThresholdDecision to RoutingDecision
            routing_decision = RoutingDecision(
                target_node=threshold_decision.target_node,
                threshold_action=threshold_decision.action,
                final_confidence=threshold_decision.final_confidence,
                intent_confidence=threshold_decision.intent_confidence,
                pattern_confidence=threshold_decision.pattern_confidence,
                rule_applied=threshold_decision.rule_applied,
                reasoning=threshold_decision.reasoning,
                timestamp=datetime.now(),
                mandatory_data_override=getattr(threshold_decision, 'mandatory_data_override', False)
            )

            # Structured telemetry for final routing decision
            app_logger.info(
                f"[SMART_ROUTER] Routing decision completed",
                extra={
                    "component": "smart_router",
                    "operation": "routing_completed",
                    "target_node": routing_decision.target_node,
                    "threshold_action": routing_decision.threshold_action,
                    "final_confidence": routing_decision.final_confidence,
                    "intent_confidence": routing_decision.intent_confidence,
                    "pattern_confidence": routing_decision.pattern_confidence,
                    "rule_applied": routing_decision.rule_applied,
                    "mandatory_data_override": getattr(routing_decision, "mandatory_data_override", False)
                }
            )

            self.routing_stats["successful_routes"] += 1
            return routing_decision

        except Exception as e:
            app_logger.error(f"Error in routing decision: {e}")
            # Return safe fallback decision
            return RoutingDecision(
                target_node="fallback",
                threshold_action="fallback_level1",
                final_confidence=0.3,
                intent_confidence=0.2,
                pattern_confidence=0.2,
                rule_applied="error_fallback",
                reasoning=f"Error in routing: {str(e)}",
                timestamp=datetime.now()
            )


    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing performance statistics"""
        success_rate = self.routing_stats["successful_routes"] / max(
            1, self.routing_stats["total_decisions"]
        )

        return {
            **self.routing_stats,
            "success_rate": success_rate,
            "active_business_rules": len([r for r in self.business_rules if r.active]),
            "total_business_rules": len(self.business_rules),
        }


# Global instance for easy access
smart_router = SmartConversationRouter()
