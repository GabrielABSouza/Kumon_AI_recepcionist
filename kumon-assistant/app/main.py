"""
FastAPI application entry point
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.v1 import whatsapp, health, units
from app.core.config import settings
from app.core.logger import app_logger

# Create FastAPI app instance
app = FastAPI(
    title="Kumon AI Receptionist",
    description="AI-powered WhatsApp receptionist for Kumon with multi-unit support",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for webhook handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    app_logger.error(f"HTTP error: {exc.detail}", extra={"status_code": exc.status_code})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    app_logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

# Include routers
# Legacy single-unit webhook (for backward compatibility)
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp-legacy"])

# New multi-unit management and webhooks
app.include_router(units.router, prefix="/api/v1", tags=["units"])

# Health and utility endpoints
app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Root path operation
@app.get("/")
async def root():
    """Root endpoint"""
    app_logger.info("Root endpoint accessed")
    return {
        "message": "Kumon AI Receptionist API",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "Multi-unit support",
            "Unit-specific webhooks",
            "WhatsApp Business API integration",
            "AI-powered responses",
            "Appointment booking"
        ],
        "docs": "/docs",
        "endpoints": {
            "legacy_webhook": "/api/v1/whatsapp/webhook",
            "unit_webhooks": "/api/v1/units/{unit_id}/webhook",
            "unit_management": "/api/v1/units"
        }
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    app_logger.info("Kumon AI Receptionist API v2.0 starting up with multi-unit support...")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    app_logger.info("Kumon AI Receptionist API shutting down...") 