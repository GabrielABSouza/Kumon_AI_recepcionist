"""
Health check routes
"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"} 

@router.delete("/reset-conversations")
async def reset_all_conversations() -> Dict[str, Any]:
    """Temporary endpoint to reset all conversation states"""
    try:
        # Import here to avoid circular import issues
        from app.services.conversation_flow import conversation_flow_manager
        
        count = len(conversation_flow_manager.conversation_states)
        conversation_flow_manager.conversation_states.clear()
        
        return {
            "message": f"All {count} conversations reset successfully", 
            "conversations_reset": count,
            "status": "success"
        }
    except Exception as e:
        return {
            "message": f"Error resetting conversations: {str(e)}", 
            "conversations_reset": 0,
            "status": "error"
        } 