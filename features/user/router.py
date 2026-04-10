# features/user/router.py - Firebase User Management API
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from firebase_admin import auth
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from .models import User
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
    db: AsyncSession = Depends(get_db)
):
    """
    List all users registered in Firebase Authentication and also users created from Admin Web.
    Returns user profiles including email, display name, photo, and sign-in providers.
    """
    try:
        users = []
        # 1. Fetch Firebase users
        try:
            page = auth.list_users(max_results=max_results)
            while page:
                for user in page.users:
                    users.append(_user_record_to_response(user))
                page = page.get_next_page()
            logger.info(f"Listed {len(users)} Firebase users")
        except Exception as e:
            logger.error(f"Error fetching Firebase users: {e}")
            # Non-blocking, continue to fetch Admin users

        # 2. Fetch Admin Web users (fake_firebase_uid starting with 'admin_')
        stmt = select(User).where(User.firebase_uid.like("admin_%"))
        result = await db.execute(stmt)
        admin_users = result.scalars().all()
        
        for u in admin_users:
            users.append(
                FirebaseUserResponse(
                    uid=u.firebase_uid,
                    email=u.email,
                    display_name=u.full_name or u.username,
                    photo_url=u.avatar_url,
                    phone_number=u.phone_number,
                    email_verified=True,
                    disabled=u.is_banned,
                    providers=["admin"],
                    creation_timestamp=int(u.created_at.timestamp() * 1000) if u.created_at else None,
                    last_sign_in_timestamp=None,
                )
            )

        return FirebaseUserListResponse(
            users=users,
            total=len(users),
        )
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve users: {e}",
        )


@router.get("/{uid}", response_model=FirebaseUserResponse)
async def get_firebase_user(uid: str, db: AsyncSession = Depends(get_db)):
    """
    Get a single user by their UID (either Firebase or Admin created).
    """
    if uid.startswith("admin_"):
        stmt = select(User).where(User.firebase_uid == uid)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail=f"User with UID '{uid}' not found")
        return FirebaseUserResponse(
            uid=user.firebase_uid,
            email=user.email,
            display_name=user.full_name or user.username,
            photo_url=user.avatar_url,
            phone_number=user.phone_number,
            email_verified=True,
            disabled=user.is_banned,
            providers=["admin"],
            creation_timestamp=int(user.created_at.timestamp() * 1000) if user.created_at else None,
            last_sign_in_timestamp=None,
        )
    else:
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

