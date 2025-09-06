"""
Minimal FastAPI application for debugging
"""
from fastapi import FastAPI

# Create FastAPI app instance
app = FastAPI(
    title="Kumon AI Receptionist - Minimal",
    description="Minimal version for debugging",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"} 