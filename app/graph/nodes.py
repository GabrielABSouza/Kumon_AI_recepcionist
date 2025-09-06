"""
Graph Node Discovery and Enumeration

This module provides the canonical source of truth for all LangGraph nodes
in the Kumon Assistant conversation workflow. It implements the contract
required by the Intent Classifier refactoring (see docs/prompt_classificador_regex.md).
"""

from typing import TypedDict, List
from enum import Enum

from app.core.state.models import ConversationStage, ConversationStep


class Node(TypedDict):
    """Node definition contract for intent classifier"""
    id: str
    purpose: str
    required_slots: list[str]
    synonyms: list[str] | None
    channels: list[str] | None   # subset of {"web","app","whatsapp"}  
    reachability: list[str] | None  # upstream/downstream ids


def enumerate_nodes() -> List[Node]:
    """
    Enumerate all LangGraph nodes in the Kumon Assistant conversation workflow.
    
    This is the canonical source of truth for intent classification.
    Every node in the LangGraph must be represented here.
    
    Returns:
        List[Node]: Complete list of all conversation nodes
    """
    
    nodes = [
        # GREETING STAGE NODES
        {
            "id": "greeting",
            "purpose": "Initial customer greeting and welcome",
            "required_slots": ["parent_name"],
            "synonyms": ["welcome", "hello", "initial_contact"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["qualification", "information"]
        },
        
        # QUALIFICATION STAGE NODES  
        {
            "id": "qualification",
            "purpose": "Collect customer qualification data (parent/child info)",
            "required_slots": ["parent_name", "child_name", "student_age", "education_level"],
            "synonyms": ["data_collection", "customer_info", "profile"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["information", "scheduling"]
        },
        
        {
            "id": "qualification_name_collection",
            "purpose": "Specifically collect parent and child names",
            "required_slots": ["parent_name", "child_name"],
            "synonyms": ["name_gathering", "identity"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["qualification_age_collection", "qualification"]
        },
        
        {
            "id": "qualification_age_collection", 
            "purpose": "Collect child age and education level",
            "required_slots": ["student_age", "education_level"],
            "synonyms": ["age_data", "school_grade"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["qualification_programs", "information"]
        },
        
        {
            "id": "qualification_programs",
            "purpose": "Identify programs of interest",
            "required_slots": ["programs_of_interest"],
            "synonyms": ["program_selection", "course_interest"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["information", "scheduling"]
        },
        
        # INFORMATION GATHERING STAGE NODES
        {
            "id": "information",
            "purpose": "Provide Kumon methodology and program information", 
            "required_slots": ["programs_of_interest"],
            "synonyms": ["info_sharing", "program_explanation"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["scheduling", "confirmation"]
        },
        
        {
            "id": "methodology_explanation",
            "purpose": "Explain Kumon methodology and approach",
            "required_slots": ["programs_of_interest"],
            "synonyms": ["method_info", "approach_details"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["program_explanation", "scheduling"]
        },
        
        {
            "id": "program_explanation",
            "purpose": "Detailed program information and benefits",
            "required_slots": ["programs_of_interest"],
            "synonyms": ["program_details", "course_info"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["scheduling", "confirmation"]
        },
        
        # SCHEDULING STAGE NODES
        {
            "id": "scheduling",
            "purpose": "Schedule assessment or trial class",
            "required_slots": ["date_preferences", "available_slots"],
            "synonyms": ["appointment", "booking", "slot_selection"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["confirmation", "validation"]
        },
        
        {
            "id": "availability_check",
            "purpose": "Check customer availability for appointments",
            "required_slots": ["date_preferences"],
            "synonyms": ["schedule_check", "time_availability"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["slot_presentation", "scheduling"]
        },
        
        {
            "id": "slot_presentation", 
            "purpose": "Present available time slots to customer",
            "required_slots": ["available_slots"],
            "synonyms": ["time_options", "appointment_slots"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["slot_selection", "confirmation"]
        },
        
        {
            "id": "slot_selection",
            "purpose": "Customer selects preferred appointment slot",
            "required_slots": ["selected_slot"],
            "synonyms": ["time_choice", "appointment_confirm"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["validation", "confirmation"]
        },
        
        # VALIDATION STAGE NODES
        {
            "id": "validation",
            "purpose": "Validate and confirm customer contact information",
            "required_slots": ["contact_email", "phone_number"],
            "synonyms": ["contact_validation", "info_confirmation"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["confirmation", "completed"]
        },
        
        {
            "id": "contact_confirmation",
            "purpose": "Confirm customer contact details",
            "required_slots": ["contact_email"],
            "synonyms": ["email_validation", "contact_check"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["confirmation", "completed"]
        },
        
        # CONFIRMATION STAGE NODES
        {
            "id": "confirmation",
            "purpose": "Final confirmation of appointment and details",
            "required_slots": ["selected_slot", "contact_email"],
            "synonyms": ["final_confirm", "appointment_confirmed"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["completed", "handoff"]
        },
        
        {
            "id": "appointment_confirmed",
            "purpose": "Appointment successfully confirmed",
            "required_slots": ["selected_slot", "contact_email", "parent_name"],
            "synonyms": ["booking_complete", "confirmed"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["completed"]
        },
        
        # COMPLETION STAGE NODES
        {
            "id": "completed",
            "purpose": "Conversation successfully completed",
            "required_slots": [],
            "synonyms": ["finished", "done", "success"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": []
        },
        
        # HANDOFF/ERROR NODES
        {
            "id": "handoff",
            "purpose": "Transfer to human agent",
            "required_slots": [],
            "synonyms": ["human_transfer", "escalation"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["completed"]
        },
        
        {
            "id": "error_recovery",
            "purpose": "Handle conversation errors and recovery",
            "required_slots": [],
            "synonyms": ["error_handling", "recovery"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["greeting", "qualification", "handoff"]
        },
        
        # UNIVERSAL NODES (can be reached from any stage)
        {
            "id": "clarification",
            "purpose": "Handle user confusion and provide clarification",
            "required_slots": [],
            "synonyms": ["help", "confusion", "unclear"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["greeting", "qualification", "information", "scheduling", "handoff"]
        },
        
        {
            "id": "objection_handling",
            "purpose": "Address customer objections and concerns",
            "required_slots": [],
            "synonyms": ["concerns", "doubts", "resistance"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["information", "scheduling", "confirmation", "handoff"]
        },
        
        # EMERGENCY PROGRESSION NODE
        {
            "id": "emergency_progression",
            "purpose": "Handle urgent customer needs and escalate appropriately",
            "required_slots": [],
            "synonyms": ["urgent", "emergency", "critical", "immediate"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["handoff", "scheduling", "information"]
        },
        
        # DELIVERY NODE (technical infrastructure)
        {
            "id": "delivery",
            "purpose": "Core message delivery and routing infrastructure",
            "required_slots": [],
            "synonyms": ["message_delivery", "routing", "dispatch"],
            "channels": ["whatsapp", "web", "app"],
            "reachability": ["END"]  # Special terminal state
        }
    ]
    
    return nodes


def get_node_by_id(node_id: str) -> Node | None:
    """
    Get a specific node by ID.
    
    Args:
        node_id: The node ID to lookup
        
    Returns:
        Node or None if not found
    """
    nodes = enumerate_nodes()
    for node in nodes:
        if node["id"] == node_id:
            return node
    return None


def get_nodes_by_stage(stage: ConversationStage) -> List[Node]:
    """
    Get all nodes belonging to a specific conversation stage.
    
    Args:
        stage: The conversation stage
        
    Returns:
        List of nodes for that stage
    """
    nodes = enumerate_nodes()
    stage_value = stage.value.lower()
    
    # Map stages to node prefixes/patterns
    stage_filters = {
        "greeting": lambda n: n["id"] in ["greeting"],
        "qualification": lambda n: n["id"].startswith("qualification") or n["id"] == "qualification",
        "information": lambda n: n["id"] in ["information", "methodology_explanation", "program_explanation"],
        "scheduling": lambda n: n["id"].startswith(("scheduling", "availability", "slot")) or n["id"] == "scheduling",
        "validation": lambda n: n["id"].startswith(("validation", "contact")) or n["id"] == "validation", 
        "confirmation": lambda n: n["id"].startswith("confirmation") or n["id"] in ["confirmation", "appointment_confirmed"],
        "completed": lambda n: n["id"] == "completed",
        "handoff": lambda n: n["id"] == "handoff"
    }
    
    filter_func = stage_filters.get(stage_value)
    if filter_func:
        return [node for node in nodes if filter_func(node)]
    
    return []


def validate_node_coverage() -> dict:
    """
    Validate that all nodes are properly defined and accessible.
    
    Returns:
        Dictionary with validation results
    """
    nodes = enumerate_nodes()
    
    # Check for duplicate IDs
    node_ids = [node["id"] for node in nodes]
    duplicates = [node_id for node_id in set(node_ids) if node_ids.count(node_id) > 1]
    
    # Check for required fields
    invalid_nodes = []
    for node in nodes:
        if not all(key in node for key in ["id", "purpose", "required_slots"]):
            invalid_nodes.append(node.get("id", "unknown"))
    
    # Check reachability (basic validation)
    unreachable_nodes = []
    all_targets = set()
    for node in nodes:
        if node["reachability"]:
            all_targets.update(node["reachability"])
    
    for target in all_targets:
        if target not in node_ids and target != "END":  # END is special terminal state
            unreachable_nodes.append(target)
    
    return {
        "total_nodes": len(nodes),
        "duplicate_ids": duplicates,
        "invalid_nodes": invalid_nodes,
        "unreachable_targets": unreachable_nodes,
        "valid": len(duplicates) == 0 and len(invalid_nodes) == 0 and len(unreachable_nodes) == 0
    }


if __name__ == "__main__":
    # Smoke test
    nodes = enumerate_nodes()
    print(f"Discovered {len(nodes)} nodes")
    
    validation = validate_node_coverage()
    print(f"Validation: {validation}")
    
    if not validation["valid"]:
        print("❌ Node enumeration failed validation")
        exit(1)
    else:
        print("✅ Node enumeration passed validation")