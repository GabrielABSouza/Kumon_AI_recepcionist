"""
FastAPI application entry point
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.v1 import whatsapp, health
from app.core.config import settings
from app.core.logger import app_logger

# Create FastAPI app instance
app = FastAPI(
    title="Kumon AI Receptionist",
    description="AI-powered WhatsApp receptionist for Kumon",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for webhook handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Root path operation
@app.get("/")
async def root():
    """Root endpoint"""
    app_logger.info("Root endpoint accessed")
    return {
        "message": "Kumon AI Receptionist API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    app_logger.info("Kumon AI Receptionist API starting up...")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    app_logger.info("Kumon AI Receptionist API shutting down...") 