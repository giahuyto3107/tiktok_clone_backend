# core/auth.py - Firebase Authentication Dependencies for FastAPI
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

# Reusable security scheme — extracts "Bearer <token>" from the Authorization header
_bearer_scheme = HTTPBearer(auto_error=True)
_bearer_scheme_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credential: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency that enforces Firebase authentication.

    - Extracts the Firebase ID token from the Authorization header.
    - Verifies the token against Firebase and returns the decoded token dict.
    - Raises 401 if the token is missing, invalid, or expired.

    The returned dict contains useful fields such as:
        uid, email, name, picture, email_verified, firebase, etc.

    Usage:
        @router.get("/me")
        async def me(user: dict = Depends(get_current_user)):
            return {"uid": user["uid"], "email": user.get("email")}
    """
    token = credential.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has expired. Please sign in again.",
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
        )


async def get_optional_user(
    credential: Optional[HTTPAuthorizationCredentials] = Depends(
        _bearer_scheme_optional
    ),
) -> Optional[dict]:
    """
    Same as get_current_user but returns None instead of 401
    when no token is provided.  Useful for endpoints that work
    for both authenticated and anonymous users.
    """
    if credential is None:
        return None

    token = credential.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        return None
