"""
Smart Router Adapter - Bridge between Core and Workflows
 
Adapter fino que conecta a nova arquitetura modular (app/workflows/)
ao pipeline de produção (app/core/), evitando ciclos de import.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..logger import app_logger
from ..state.models import CeciliaState, ConversationStage, ConversationStep


@dataclass
class CoreRoutingDecision:
    """Simplified routing decision for core integration"""
    target_node: str
    confidence: float
    reasoning: str
    rule_applied: str
    intent_confidence: float = 0.0
    pattern_confidence: float = 0.0
    threshold_action: str = "proceed"
    mandatory_data_override: bool = False


class SmartRouterAdapter:
    """
    Adapter that bridges core routing to modular SmartRouter
    
    Responsibilities:
    - Import workflows SmartRouter safely
    - Convert between core and workflows data structures  
    - Provide fallback to legacy routing
    - Handle enum conversions
    """
    
    def __init__(self):
        self._smart_router = None
        self._fallback_enabled = True
        app_logger.info("[ADAPTER] SmartRouterAdapter initialized")
    
    async def _get_smart_router(self):
        """Lazy load SmartRouter to avoid import cycles"""
        if self._smart_router is None:
            try:
                from ...workflows.smart_router import smart_router
                self._smart_router = smart_router
                app_logger.info("[ADAPTER] SmartRouter loaded successfully")
            except ImportError as e:
                app_logger.error(f"[ADAPTER] Failed to import SmartRouter: {e}")
                self._smart_router = None
        return self._smart_router
    
    async def decide_route(
        self, 
        state: CeciliaState,
        current_function: str = "unknown"
    ) -> CoreRoutingDecision:
        """
        Main decision method that integrates modular SmartRouter
        
        Args:
            state: Current conversation state
            current_function: Name of calling function for telemetry
            
        Returns:
            CoreRoutingDecision: Simplified decision for core consumption
        """
        try:
            # Structured telemetry for adapter usage
            app_logger.info(
                f"[ADAPTER] Processing routing decision",
                extra={
                    "component": "smart_router_adapter",
                    "operation": "decide_route", 
                    "current_function": current_function,
                    "phone_number": state.get("phone_number", "unknown")[-4:],
                    "current_stage": state.get("current_stage", ConversationStage.GREETING).value
                }
            )
            
            smart_router = await self._get_smart_router()
            
            if smart_router is None:
                return self._fallback_decision(state, "smart_router_unavailable")
            
            # 1. Classify intent first (SmartRouterAdapter responsibility)
            from ...core.dependencies import intent_classifier
            
            intent_result = await intent_classifier.classify_intent(
                state["last_user_message"], state
            )
            
            # 2. Call modular SmartRouter with classified data
            routing_decision = await smart_router.make_routing_decision(
                state=state,
                intent_result=intent_result
            )
            
            # Convert to CoreRoutingDecision
            core_decision = CoreRoutingDecision(
                target_node=routing_decision.target_node,
                confidence=routing_decision.final_confidence,
                reasoning=routing_decision.reasoning,
                rule_applied=routing_decision.rule_applied,
                intent_confidence=routing_decision.intent_confidence,
                pattern_confidence=routing_decision.pattern_confidence,
                threshold_action=routing_decision.threshold_action,
                mandatory_data_override=getattr(routing_decision, 'mandatory_data_override', False)
            )
            
            # Store routing_info in state for telemetry and ResponsePlanner
            state["routing_info"] = {
                "target_node": core_decision.target_node,
                "final_confidence": core_decision.confidence,
                "intent_confidence": core_decision.intent_confidence,
                "pattern_confidence": core_decision.pattern_confidence,
                "threshold_action": core_decision.threshold_action,
                "rule_applied": core_decision.rule_applied,
                "reasoning": core_decision.reasoning,
                "intent_category": intent_result.category,  # For ResponsePlanner template mapping
                "timestamp": datetime.now().isoformat(),
                "adapter_version": "1.0",
                "source": "modular_smart_router"
            }
            
            # Success telemetry
            app_logger.info(
                f"[ADAPTER] Routing decision completed",
                extra={
                    "component": "smart_router_adapter",
                    "operation": "decision_success",
                    "target_node": core_decision.target_node,
                    "confidence": core_decision.confidence,
                    "threshold_action": core_decision.threshold_action,
                    "rule_applied": core_decision.rule_applied
                }
            )
            
            return core_decision
            
        except Exception as e:
            app_logger.error(
                f"[ADAPTER] Error in routing decision: {e}",
                extra={
                    "component": "smart_router_adapter",
                    "operation": "decision_error", 
                    "error": str(e),
                    "fallback_enabled": self._fallback_enabled
                }
            )
            return self._fallback_decision(state, f"adapter_error: {e}")
    
    def _fallback_decision(self, state: CeciliaState, reason: str) -> CoreRoutingDecision:
        """Generate safe fallback decision when SmartRouter fails"""
        current_stage = state.get("current_stage", ConversationStage.GREETING)
        
        # Simple stage-based fallback logic
        if current_stage == ConversationStage.GREETING:
            target = "qualification"
        elif current_stage == ConversationStage.QUALIFICATION:
            target = "information"  
        elif current_stage == ConversationStage.INFORMATION_GATHERING:
            target = "scheduling"
        elif current_stage == ConversationStage.SCHEDULING:
            target = "validation"
        else:
            target = "handoff"
        
        fallback_decision = CoreRoutingDecision(
            target_node=target,
            confidence=0.5,  # Medium confidence for fallback
            reasoning=f"Fallback routing: {reason}",
            rule_applied="fallback_adapter",
            threshold_action="fallback_level1"
        )
        
        # Store fallback routing_info
        state["routing_info"] = {
            "target_node": fallback_decision.target_node,
            "final_confidence": fallback_decision.confidence,
            "intent_confidence": 0.3,
            "pattern_confidence": 0.3,
            "threshold_action": fallback_decision.threshold_action,
            "rule_applied": fallback_decision.rule_applied,
            "reasoning": fallback_decision.reasoning,
            "timestamp": datetime.now().isoformat(),
            "adapter_version": "1.0",
            "source": "fallback_adapter",
            "fallback_reason": reason
        }
        
        app_logger.warning(
            f"[ADAPTER] Using fallback routing",
            extra={
                "component": "smart_router_adapter",
                "operation": "fallback_decision",
                "target_node": target,
                "reason": reason,
                "current_stage": current_stage.value
            }
        )
        
        return fallback_decision


# Global singleton instance
smart_router_adapter = SmartRouterAdapter()


def routing_mode_from_decision(rd) -> str:
    """
    Converte RoutingDecision (threshold_action + flags) em modo interno do ResponsePlanner:
    "template" | "llm_rag" | "handoff" | "fallback_l1" | "fallback_l2"
    """
    ta = getattr(rd, "threshold_action", None)
    if getattr(rd, "stage_progression_blocked", False):
        return "handoff"
    mapping = {
        "proceed": "template",
        "enhance_with_llm": "llm_rag", 
        "escalate_human": "handoff",
        "fallback_level1": "fallback_l1",
        "fallback_level2": "fallback_l2",
        # se houver "clarify" em threshold_action, trate como fallback_l1
        "clarify": "fallback_l1",
    }
    return mapping.get(ta, "fallback_l2")


def normalize_rd_obj(rd_obj):
    """Permite rd como dataclass ou dict."""
    if isinstance(rd_obj, dict):
        class RD: pass
        r = RD()
        for k, v in rd_obj.items(): setattr(r, k, v)
        return r
    return rd_obj