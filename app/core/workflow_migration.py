# app/core/workflow_migration.py
"""
Workflow Migration - New Perception → Decision → Action → Delivery Pipeline

This module implements the migrated StateGraph with clean separation:
STAGE_RESOLVER → SMART_ROUTER → RESPONSE_PLANNER → DELIVERY → loop

Replaces existing DELIVERY mega-node with proper architectural separation.
"""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .state.models import CeciliaState
from .nodes.stage_resolver import stage_resolver_node
from .router.delivery_io import delivery_node  
from .router.routing_and_planning import routing_and_planning_node

logger = logging.getLogger(__name__)


def should_continue(state: dict) -> str:
    """
    Loop termination logic with explicit criteria and anti-loop fail-safes
    
    Stops when:
    1. should_end flag is set (from delivery_io or error handling)
    2. handoff or completed stage reached
    3. outbox is empty AND stage/slots unchanged from last iteration
    4. max_iters exceeded (safety net)
    
    Returns:
        str: "STAGE_RESOLVER" to continue loop, "END" to terminate
    """
    
    current_stage = state.get("current_stage")
    
    # Anti-loop fail-safe: Check should_end flag first
    if state.get("should_end", False):
        stop_reason = state.get("stop_reason", "unknown")
        logger.info(f"Workflow terminated by fail-safe: {stop_reason}")
        return "END"
    
    # Terminal conditions
    if current_stage in ["completed", "handoff"]:
        logger.info(f"Workflow terminated: stage={current_stage}")
        return "END"
    
    # Check for loop completion
    outbox = state.get("outbox", [])
    prev_stage = state.get("_prev_stage")
    prev_slots = state.get("_prev_slots")
    current_slots = state.get("required_slots")
    
    # If outbox empty and stage/slots unchanged, we're done
    if (not outbox and 
        prev_stage == current_stage and 
        prev_slots == current_slots):
        logger.info("Workflow terminated: no changes detected")
        return "END"
    
    # Safety net: max iterations (reduced from 25 to 5)
    iterations = state.get("_iterations", 0)
    if iterations >= 5:
        logger.warning(f"Workflow terminated: max iterations exceeded ({iterations})")
        state["should_end"] = True
        state["stop_reason"] = "max_iterations_exceeded"
        return "END"
    
    # Continue loop
    state["_iterations"] = iterations + 1
    state["_prev_stage"] = current_stage
    state["_prev_slots"] = current_slots
    
    logger.debug(f"Workflow continuing: iteration {iterations + 1}, stage={current_stage}")
    return "STAGE_RESOLVER"


def create_migrated_workflow() -> StateGraph:
    """
    Create new perception→decision→action→delivery workflow
    
    Pipeline:
    1. STAGE_RESOLVER: Infer stage + required_slots (perception)
    2. ROUTING_AND_PLANNING: Make routing_decision + enqueue messages (combined decision+action)
    3. DELIVERY: Emit messages + update state (IO-only delivery)
    4. Loop with termination criteria
    
    Returns:
        StateGraph: Configured workflow ready for execution
    """
    
    logger.info("Creating migrated perception→decision→action→delivery workflow")
    
    # Initialize StateGraph
    workflow = StateGraph(CeciliaState)
    
    # ========== ADD NODES ==========
    workflow.add_node("STAGE_RESOLVER", stage_resolver_node)
    workflow.add_node("ROUTING_AND_PLANNING", routing_and_planning_node)
    workflow.add_node("DELIVERY", delivery_node)
    
    # ========== SET ENTRY POINT ==========
    workflow.set_entry_point("STAGE_RESOLVER")
    
    # ========== ADD EDGES ==========
    # Linear pipeline
    workflow.add_edge("STAGE_RESOLVER", "ROUTING_AND_PLANNING")
    workflow.add_edge("ROUTING_AND_PLANNING", "DELIVERY")
    
    # Loop with termination criteria
    workflow.add_conditional_edges(
        "DELIVERY",
        should_continue,
        {
            "STAGE_RESOLVER": "STAGE_RESOLVER",  # Continue loop
            "END": END                           # Terminate
        }
    )
    
    logger.info("Migrated workflow created successfully")
    return workflow


def ensure_state_compatibility(state: dict) -> dict:
    """
    Ensure state compatibility with new workflow
    
    Adds required fields for migration:
    - outbox for MessageEnvelope pattern
    - Loop tracking variables
    - Channel configuration
    """
    
    # Core requirements
    state.setdefault("outbox", [])
    state.setdefault("_iterations", 0) 
    state.setdefault("_emitted_ids", [])
    state.setdefault("default_channel", "whatsapp")
    
    # Tracking for loop termination
    state.setdefault("_prev_stage", None)
    state.setdefault("_prev_slots", None)
    
    return state


# ========== CECILIA WORKFLOW SINGLETON ==========

_cecilia_singleton = None

def get_cecilia_workflow():
    """
    Get or create CeciliaWorkflow singleton instance (V2 migrated version)
    
    Returns:
        StateGraph: Compiled migrated workflow ready for execution
    """
    global _cecilia_singleton
    if _cecilia_singleton is None:
        logger.info("Creating CeciliaWorkflow singleton (V2 migrated)")
        workflow = create_migrated_workflow()
        _cecilia_singleton = workflow.compile()
        logger.info("CeciliaWorkflow V2 compiled and ready")
    return _cecilia_singleton


# Export for backward compatibility
__all__ = [
    "get_cecilia_workflow", 
    "create_migrated_workflow",
    "ensure_state_compatibility",
    "should_continue"
]