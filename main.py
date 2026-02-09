# main.py - FastAPI Application Entry Point
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import init_db
from features.video.router import router as video_router

# Create upload directories
UPLOAD_RAW_DIR = "uploads/raw"
UPLOAD_COMPRESSED_DIR = "uploads/compressed"

os.makedirs(UPLOAD_RAW_DIR, exist_ok=True)
os.makedirs(UPLOAD_COMPRESSED_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Initialize database tables
    await init_db()
    print("✅ Database initialized")
    yield
    # Shutdown: Cleanup if needed
    print("👋 Application shutting down")


app = FastAPI(
    title="TikTok Clone API",
    description="Backend API for TikTok Clone Application",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files for serving videos
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(video_router, prefix="/api/v1/videos", tags=["Videos"])


@app.get("/")
async def root():
    return {"message": "TikTok Clone API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
