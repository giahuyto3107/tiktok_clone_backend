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
