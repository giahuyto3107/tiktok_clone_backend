# features/user/router.py - Firebase User Management API
import logging

from fastapi import APIRouter, HTTPException, Query
from firebase_admin import auth

from .schemas import FirebaseUserResponse, FirebaseUserListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _user_record_to_response(user: auth.UserRecord) -> FirebaseUserResponse:
    """Convert a Firebase UserRecord to our response schema."""
    providers = [
        p.provider_id for p in (user.provider_data or [])
    ]

    return FirebaseUserResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        photo_url=user.photo_url,
        phone_number=user.phone_number,
        email_verified=user.email_verified,
        disabled=user.disabled,
        providers=providers,
        creation_timestamp=user.user_metadata.creation_timestamp if user.user_metadata else None,
        last_sign_in_timestamp=user.user_metadata.last_sign_in_timestamp if user.user_metadata else None,
    )


@router.get("", response_model=FirebaseUserListResponse)
async def list_firebase_users(
    max_results: int = Query(default=1000, ge=1, le=1000, description="Max users to return"),
):
    """
    List all users registered in Firebase Authentication.
    Returns user profiles including email, display name, photo, and sign-in providers.
    """
    try:
        users = []
        page = auth.list_users(max_results=max_results)

        while page:
            for user in page.users:
                users.append(_user_record_to_response(user))
            # Get next page (None if no more pages)
            page = page.get_next_page()

        logger.info(f"Listed {len(users)} Firebase users")

        return FirebaseUserListResponse(
            users=users,
            total=len(users),
        )
    except Exception as e:
        logger.error(f"Failed to list Firebase users: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve Firebase users: {e}",
        )


@router.get("/{uid}", response_model=FirebaseUserResponse)
async def get_firebase_user(uid: str):
    """
    Get a single Firebase user by their UID.
    """
    try:
        user = auth.get_user(uid)
        return _user_record_to_response(user)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User with UID '{uid}' not found")
    except Exception as e:
        logger.error(f"Failed to get Firebase user {uid}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user: {e}",
        )

import os
import uuid
from fastapi import UploadFile, File

UPLOAD_AVATARS_DIR = "uploads/images/avatars"
os.makedirs(UPLOAD_AVATARS_DIR, exist_ok=True)
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

@router.post("/upload_avatar")
async def upload_avatar(
    file: UploadFile = File(...)
):
    """
    Upload an avatar image to the local backend.
    Returns the local URL to the uploaded avatar.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}",
        )

    # Read content to check size (e.g. limit to 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")

    unique_filename = f"avatar_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_AVATARS_DIR, unique_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved avatar: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save avatar file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save avatar image")

    # The backend is serving /uploads folder using StaticFiles
    avatar_url = f"/uploads/images/avatars/{unique_filename}"
    
    return {
        "status": "success",
        "avatarUrl": avatar_url
    }
