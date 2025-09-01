"""
Routing Node - Centralized Routing and Response Planning

This is the dedicated ROUTING node that centralizes all routing decisions 
and response planning, following the corrected architecture:

Stage Node → Simple Edge → ROUTING Node → DELIVERY Node → DeliveryService
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
import logging

from ..state.models import CeciliaState
from ..router.smart_router_adapter import smart_router_adapter
from ..router.response_planner import response_planner

logger = logging.getLogger(__name__)


async def routing_node(state: CeciliaState) -> CeciliaState:
    """
    ROUTING Node - Centralized routing and response planning
    
    This node:
    1. Calls smart_router_adapter.decide_route() for routing decision
    2. Calls response_planner.plan_and_generate() for response generation  
    3. Modifies state with routing_decision and planned_response
    4. Prepares for DELIVERY node to package delivery_ready
    
    Args:
        state: Current conversation state (after Stage Node execution)
        
    Returns:
        Updated state with routing decisions and planned response
    """
    phone_number = state.get("phone_number", "unknown")
    current_node = state.get("last_node", "unknown")
    
    logger.info(f"🎯 ROUTING NODE: Processing routing for {phone_number[-4:]} from {current_node}")
    
    try:
        # STEP 1: SmartRouter decision
        logger.info(f"🧠 ROUTING NODE: Calling SmartRouter for {current_node}")
        routing_decision = await smart_router_adapter.decide_route(
            state, f"routing_from_{current_node}"
        )
        
        # STEP 2: ResponsePlanner generates planned_response  
        logger.info(f"📝 ROUTING NODE: Calling ResponsePlanner for {current_node}")
        await response_planner.plan_and_generate(state, routing_decision)
        # planned_response is now in state["planned_response"]
        
        # STEP 3: Store routing decision in state (Nodes CAN modify state)
        state["routing_decision"] = {
            "target_node": routing_decision.target_node,
            "threshold_action": routing_decision.threshold_action,
            "confidence": routing_decision.confidence,
            "reasoning": routing_decision.reasoning,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # STEP 4: Mark routing completion
        state["routing_complete"] = True
        state["routing_timestamp"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            f"✅ ROUTING NODE: Completed - {current_node} → {routing_decision.target_node} "
            f"(action: {routing_decision.threshold_action}, confidence: {routing_decision.confidence:.2f})"
        )
        
        return state
        
    except Exception as e:
        logger.error(f"🚨 ROUTING NODE error for {phone_number}: {e}")
        
        # Generate fallback routing decision
        fallback_decision = {
            "target_node": "handoff",
            "threshold_action": "escalate_human",
            "confidence": 0.0,
            "reasoning": f"Emergency fallback due to routing error: {e}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Store fallback info
        state["routing_decision"] = fallback_decision
        state["planned_response"] = "Desculpe, houve um problema técnico. Nossa equipe entrará em contato: (51) 99692-1999"
        state["routing_complete"] = True
        state["routing_error"] = str(e)
        
        logger.warning(f"⚠️ ROUTING NODE: Used fallback for {phone_number} due to error")
        
        return state