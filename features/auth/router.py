# features/auth/router.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from firebase_admin import auth

from database import get_db
from features.user.repository import UserRepository
from .schemas import LoginRequest, LoginResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user using Firebase ID Token.
    If user doesn't exist in local DB, create them.
    """
    try:
        # Verify the ID token first
        decoded_token = auth.verify_id_token(request.id_token)
        uid = decoded_token['uid']
        
        # Get user details from Firebase
        firebase_user = auth.get_user(uid)
        
        # Try finding in our local DB
        user_repo = UserRepository(db)
        local_user = await user_repo.get_by_firebase_uid(uid)
        
        if not local_user:
            # Create user
            local_user = await user_repo.create_user(
                firebase_uid=uid,
                email=firebase_user.email,
                phone_number=firebase_user.phone_number,
                full_name=firebase_user.display_name,
                avatar_url=firebase_user.photo_url,
                date_of_birth=request.date_of_birth
            )
            logger.info(f"Created new local user for Firebase UID {uid}")
        else:
            logger.info(f"Logged in existing user Firebase UID {uid}")

        return LoginResponse(
            user=local_user,
            access_token=request.id_token, # Send back Firebase token as access token for simplicity
            token_type="bearer"
        )
        
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase ID Token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired Firebase ID Token")
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during login")
