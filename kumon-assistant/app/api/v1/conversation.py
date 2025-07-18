"""
Conversation API endpoints for managing conversation flow and progress
"""
from fastapi import APIRouter, HTTPException, Path, Query
from typing import Dict, Any

from app.services.conversation_flow import conversation_flow_manager
from app.core.logger import app_logger

router = APIRouter()


@router.get("/conversation/{phone_number}/progress")
async def get_conversation_progress(
    phone_number: str = Path(..., description="Phone number")
) -> Dict[str, Any]:
    """Get conversation progress for a phone number"""
    try:
        progress = conversation_flow_manager.get_conversation_progress(phone_number)
        return progress
    except Exception as e:
        app_logger.error(f"Error getting conversation progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get conversation progress")


@router.delete("/conversation/{phone_number}")
async def reset_conversation(
    phone_number: str = Path(..., description="Phone number")
) -> Dict[str, str]:
    """Reset conversation state for a phone number"""
    try:
        if phone_number in conversation_flow_manager.conversation_states:
            del conversation_flow_manager.conversation_states[phone_number]
            app_logger.info(f"Reset conversation for {phone_number}")
            return {"message": f"Conversation reset for {phone_number}"}
        else:
            return {"message": f"No active conversation found for {phone_number}"}
    except Exception as e:
        app_logger.error(f"Error resetting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset conversation")


@router.get("/conversation/roadmap")
async def get_roadmap() -> Dict[str, Any]:
    """Get the conversation roadmap structure"""
    try:
        roadmap_info = {}
        for stage, info in conversation_flow_manager.roadmap.items():
            roadmap_info[stage.value] = {
                "name": info["name"],
                "description": info["description"],
                "steps": [step.value for step in info["steps"]],
                "required_data": info["required_data"],
                "next_stage": info["next_stage"].value if info["next_stage"] else None
            }
        return roadmap_info
    except Exception as e:
        app_logger.error(f"Error getting roadmap: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get roadmap")


@router.get("/conversation/active")
async def get_active_conversations() -> Dict[str, Any]:
    """Get all active conversations"""
    try:
        active_conversations = {}
        for phone, state in conversation_flow_manager.conversation_states.items():
            active_conversations[phone] = {
                "stage": state.stage.value,
                "step": state.step.value,
                "created_at": state.created_at.isoformat(),
                "updated_at": state.updated_at.isoformat(),
                "completed_steps": len(state.completed_steps),
                "collected_data_keys": list(state.data.keys())
            }
        
        return {
            "total_active": len(active_conversations),
            "conversations": active_conversations
        }
    except Exception as e:
        app_logger.error(f"Error getting active conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get active conversations")


@router.post("/conversation/{phone_number}/simulate")
async def simulate_conversation_step(
    phone_number: str = Path(..., description="Phone number"),
    user_input: str = Query(..., description="User input to simulate")
) -> Dict[str, Any]:
    """Simulate a conversation step for testing"""
    try:
        response = await conversation_flow_manager.advance_conversation(phone_number, user_input)
        state = conversation_flow_manager.get_conversation_state(phone_number)
        
        return {
            "user_input": user_input,
            "response": response,
            "current_stage": state.stage.value,
            "current_step": state.step.value,
            "collected_data": state.data
        }
    except Exception as e:
        app_logger.error(f"Error simulating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to simulate conversation") 