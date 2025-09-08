"""
Minimal FastAPI application for ONE_TURN architecture.
Single endpoint: /webhook for Evolution API.
"""
from fastapi import FastAPI

from app.api.evolution import router as evolution_router

# Create FastAPI app
app = FastAPI(
    title="Kumon Assistant - ONE_TURN",
    description="Minimal WhatsApp assistant with 1 message → 1 response → END",
    version="1.0.0",
)

# Include Evolution API webhook router
app.include_router(evolution_router, prefix="/api/v1/evolution")


# Health check
@app.get("/")
async def root():
    return {"status": "ok", "architecture": "ONE_TURN"}


@app.get("/health")
async def health():
    return {"status": "healthy", "mode": "ONE_TURN"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
