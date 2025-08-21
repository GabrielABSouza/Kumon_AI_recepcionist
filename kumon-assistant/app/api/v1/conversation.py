"""
Conversation API endpoints for managing conversation flow and progress
"""
from fastapi import APIRouter, HTTPException, Path, Query
from typing import Dict, Any

from app.core.workflow import cecilia_workflow
from app.core.logger import app_logger

router = APIRouter()


@router.get("/conversation/{phone_number}/progress")
async def get_conversation_progress(
    phone_number: str = Path(..., description="Phone number")
) -> Dict[str, Any]:
    """Get conversation progress for a phone number using CeciliaWorkflow"""
    try:
        # Get conversation state from CeciliaWorkflow
        thread_id = f"thread_{phone_number}"
        conversation_state = await cecilia_workflow.get_conversation_state(thread_id)
        
        if conversation_state:
            progress = {
                "phone_number": phone_number,
                "stage": conversation_state.get("current_stage"),
                "step": conversation_state.get("current_step"),
                "collected_data": conversation_state.get("collected_data", {}),
                "metrics": conversation_state.get("conversation_metrics", {}),
                "workflow_system": "cecilia_langgraph"
            }
        else:
            progress = {
                "phone_number": phone_number,
                "stage": "greeting",
                "step": "welcome",
                "collected_data": {},
                "metrics": {},
                "workflow_system": "cecilia_langgraph",
                "status": "no_active_conversation"
            }
            
        return progress
    except Exception as e:
        app_logger.error(f"Error getting conversation progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get conversation progress")


@router.delete("/conversation/{phone_number}")
async def reset_conversation(
    phone_number: str = Path(..., description="Phone number")
) -> Dict[str, str]:
    """Reset conversation state for a phone number using CeciliaWorkflow"""
    try:
        thread_id = f"thread_{phone_number}"
        success = await cecilia_workflow.reset_conversation(thread_id)
        
        if success:
            app_logger.info(f"Reset conversation for {phone_number}")
            return {"message": f"Conversation reset for {phone_number}", "workflow_system": "cecilia_langgraph"}
        else:
            return {"message": f"No active conversation found for {phone_number}", "workflow_system": "cecilia_langgraph"}
    except Exception as e:
        app_logger.error(f"Error resetting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset conversation")


@router.delete("/conversations/all")
async def reset_all_conversations() -> Dict[str, Any]:
    """Reset all conversation states - CeciliaWorkflow manages state persistence"""
    try:
        # Note: CeciliaWorkflow uses PostgreSQL persistence, so this is a different operation
        app_logger.info("Reset all conversations requested - CeciliaWorkflow uses persistent state")
        return {
            "message": "CeciliaWorkflow uses persistent state management - individual resets recommended", 
            "workflow_system": "cecilia_langgraph",
            "note": "Use individual conversation reset endpoints instead"
        }
    except Exception as e:
        app_logger.error(f"Error in reset all conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process reset request")


@router.get("/conversation/roadmap")
async def get_roadmap() -> Dict[str, Any]:
    """Get the CeciliaWorkflow conversation roadmap structure"""
    try:
        # CeciliaWorkflow roadmap based on LangGraph nodes
        roadmap_info = {
            "greeting": {
                "name": "Greeting",
                "description": "Initial greeting and introduction",
                "steps": ["welcome", "initial_response", "parent_name_collection", "child_name_collection"],
                "required_data": ["parent_name", "child_name"],
                "next_stage": "qualification"
            },
            "qualification": {
                "name": "Student Qualification",
                "description": "Collect student age and education level",
                "steps": ["child_age_inquiry", "current_school_grade"],
                "required_data": ["student_age", "education_level"],
                "next_stage": "information_gathering"
            },
            "information_gathering": {
                "name": "Information Gathering",
                "description": "Share Kumon methodology and program details",
                "steps": ["methodology_explanation", "program_details"],
                "required_data": ["programs_of_interest"],
                "next_stage": "scheduling"
            },
            "scheduling": {
                "name": "Appointment Scheduling",
                "description": "Schedule evaluation appointment",
                "steps": ["availability_check", "date_preference", "time_selection", "email_collection"],
                "required_data": ["selected_slot", "contact_email"],
                "next_stage": "confirmation"
            },
            "confirmation": {
                "name": "Appointment Confirmation",
                "description": "Confirm appointment details",
                "steps": ["appointment_confirmed"],
                "required_data": [],
                "next_stage": "completed"
            }
        }
        
        return {
            "workflow_system": "cecilia_langgraph",
            "roadmap": roadmap_info
        }
    except Exception as e:
        app_logger.error(f"Error getting roadmap: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get roadmap")


@router.get("/conversation/active")
async def get_active_conversations() -> Dict[str, Any]:
    """Get active conversations from CeciliaWorkflow (limited data available)"""
    try:
        # Note: CeciliaWorkflow uses PostgreSQL persistence, active state not directly accessible
        # This endpoint now provides system information instead
        
        return {
            "workflow_system": "cecilia_langgraph",
            "persistence_method": "postgresql",
            "message": "CeciliaWorkflow uses persistent state - active conversations not directly enumerable",
            "available_operations": [
                "GET /conversation/{phone_number}/progress - Get specific conversation",
                "DELETE /conversation/{phone_number} - Reset specific conversation",
                "POST /conversation/{phone_number}/simulate - Test conversation"
            ]
        }
    except Exception as e:
        app_logger.error(f"Error getting active conversations info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get conversation info")


@router.post("/conversation/{phone_number}/simulate")
async def simulate_conversation_step(
    phone_number: str = Path(..., description="Phone number"),
    user_input: str = Query(..., description="User input to simulate")
) -> Dict[str, Any]:
    """Simulate a conversation step using CeciliaWorkflow"""
    try:
        # Process message through CeciliaWorkflow
        workflow_result = await cecilia_workflow.process_message(
            phone_number=phone_number,
            user_message=user_input
        )
        
        # Get current state
        thread_id = f"thread_{phone_number}"
        conversation_state = await cecilia_workflow.get_conversation_state(thread_id)
        
        return {
            "user_input": user_input,
            "response": workflow_result.get("response"),
            "current_stage": workflow_result.get("stage"),
            "current_step": workflow_result.get("step"),
            "collected_data": conversation_state.get("collected_data", {}) if conversation_state else {},
            "processing_time_ms": workflow_result.get("processing_time_ms"),
            "workflow_system": "cecilia_langgraph",
            "success": workflow_result.get("success")
        }
    except Exception as e:
        app_logger.error(f"Error simulating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to simulate conversation") 