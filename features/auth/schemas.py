# features/auth/schemas.py
from typing import Optional
from datetime import date
from pydantic import BaseModel
from features.user.schemas import UserProfileResponse

class LoginRequest(BaseModel):
    id_token: str
    date_of_birth: Optional[date] = None

class LoginResponse(BaseModel):
    user: UserProfileResponse
    # Could include a custom JWT here if we don't just rely on Firebase token for API calls.
    # We will rely on Firebase token as Bearer token for now, to keep it simple,
    # or you can issue an internal access_token. Let's just return the user profile.
    access_token: Optional[str] = None
    token_type: str = "bearer"
