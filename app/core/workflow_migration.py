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
from .router.delivery_io import smart_router_node, delivery_node  
from .router.response_planner import response_planner_node

logger = logging.getLogger(__name__)


def should_continue(state: dict) -> str:
    """
    Loop termination logic with explicit criteria
    
    Stops when:
    1. handoff or completed stage reached
    2. outbox is empty AND stage/slots unchanged from last iteration
    3. max_iters exceeded (safety net)
    
    Returns:
        str: "STAGE_RESOLVER" to continue loop, "END" to terminate
    """
    
    current_stage = state.get("current_stage")
    
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
    
    # Safety net: max iterations
    iterations = state.get("_iterations", 0)
    if iterations >= 3:
        logger.warning("Workflow terminated: max iterations exceeded")
        return "END"
    
    # Continue loop
    state["_iterations"] = iterations + 1
    state["_prev_stage"] = current_stage
    state["_prev_slots"] = current_slots
    
    return "STAGE_RESOLVER"


def create_migrated_workflow() -> StateGraph:
    """
    Create new perception→decision→action→delivery workflow
    
    Pipeline:
    1. STAGE_RESOLVER: Infer stage + required_slots (perception)
    2. SMART_ROUTER: Make routing_decision (decision) 
    3. RESPONSE_PLANNER: Enqueue MessageEnvelope (action)
    4. DELIVERY: Emit messages + update state (delivery)
    5. Loop with termination criteria
    
    Returns:
        StateGraph: Configured workflow ready for execution
    """
    
    logger.info("Creating migrated perception→decision→action→delivery workflow")
    
    # Initialize StateGraph
    workflow = StateGraph(CeciliaState)
    
    # ========== ADD NODES ==========
    workflow.add_node("STAGE_RESOLVER", stage_resolver_node)
    workflow.add_node("SMART_ROUTER", smart_router_node) 
    workflow.add_node("RESPONSE_PLANNER", response_planner_node)
    workflow.add_node("DELIVERY", delivery_node)
    
    # ========== SET ENTRY POINT ==========
    workflow.set_entry_point("STAGE_RESOLVER")
    
    # ========== ADD EDGES ==========
    # Linear pipeline
    workflow.add_edge("STAGE_RESOLVER", "SMART_ROUTER")
    workflow.add_edge("SMART_ROUTER", "RESPONSE_PLANNER") 
    workflow.add_edge("RESPONSE_PLANNER", "DELIVERY")
    
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