"""
WhatsApp webhook routes
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/webhook")
async def verify_webhook():
    """Verify WhatsApp webhook"""
    return {"status": "ok"}

@router.post("/webhook")
async def handle_webhook():
    """Handle WhatsApp webhook"""
    return {"status": "processed"} 