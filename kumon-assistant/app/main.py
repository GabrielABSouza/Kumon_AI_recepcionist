"""
FastAPI application entry point
"""
from fastapi import FastAPI
from app.api.v1 import whatsapp, health
from app.core.config import settings

app = FastAPI(
    title="Kumon AI Receptionist",
    description="AI-powered WhatsApp receptionist for Kumon",
    version="1.0.0"
)

# Include routers
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])

@app.get("/")
async def root():
    return {"message": "Kumon AI Receptionist API"} 