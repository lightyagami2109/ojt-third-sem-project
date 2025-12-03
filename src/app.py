"""FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.endpoints import router

app = FastAPI(
    title="Catalog Image Processing Pipeline",
    description="Async image processing with idempotency and perceptual hashing",
    version="1.0.0"
)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Catalog Image Processing Pipeline",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /v1/images",
            "get": "GET /v1/images/{asset_id}",
            "compare": "POST /v1/compare",
            "purge": "POST /v1/purge",
            "metrics": "GET /v1/metrics"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

