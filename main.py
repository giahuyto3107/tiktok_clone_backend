# main.py - FastAPI Application Entry Point
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from core.firebase import init_firebase
from features.post.router import router as post_router
from features.user.router import router as user_router
from features.social.router import router as social_router
from features.inbox.router import router as inbox_router
from features.admin.router import router as admin_router
from features.realtime.router import router as realtime_router
from features.search.router import router as search_router
from features.search.router_frontend import router as search_frontend_router

# Create upload directories (raw, compressed, images, thumbnails for video)
UPLOAD_RAW_DIR = "uploads/raw"
UPLOAD_COMPRESSED_DIR = "uploads/compressed"
UPLOAD_IMAGES_DIR = "uploads/images"
UPLOAD_THUMBNAILS_DIR = "uploads/thumbnails"

os.makedirs(UPLOAD_RAW_DIR, exist_ok=True)
os.makedirs(UPLOAD_COMPRESSED_DIR, exist_ok=True)
os.makedirs(UPLOAD_IMAGES_DIR, exist_ok=True)
os.makedirs(UPLOAD_THUMBNAILS_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Initialize database tables
    await init_db()
    print("[OK] Database initialized")

    # Startup: Initialize Firebase Admin SDK
    init_firebase()
    yield
    # Shutdown: Cleanup if needed
    print("[INFO] Application shutting down")


app = FastAPI(
    title="TikTok Clone API",
    description="Backend API for TikTok Clone Application",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for development; restrict in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Mount static files for serving media (videos + images)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.include_router(social_router, prefix="/api/v1/social", tags=["Social"])
app.include_router(post_router, prefix="/api/v1/posts", tags=["Posts"])
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(inbox_router, prefix="/api/v1/inbox", tags=["Inbox"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(realtime_router)
app.include_router(search_router, prefix="/api/v1/search", tags=["Search"])
app.include_router(search_frontend_router, prefix="/search", tags=["Search (Frontend)"])


@app.get("/api/v1")
async def api_v1_root():
    return {
        "message": "TikTok Clone API v1",
        "routes": {
            "posts": "/api/v1/posts",
            "docs": "/docs",
            "health": "/health",
        },
    }


@app.get("/")
async def root():
    return {"message": "TikTok Clone API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    print("[INFO] Starting server with HTTP")
    print("   Access at: http://YOUR_WIFI_IP:8000")
    print("   Note: Configure Android app to allow cleartext HTTP (see docs/ANDROID_CLEARTEXT_SETUP.md)")
    print()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
