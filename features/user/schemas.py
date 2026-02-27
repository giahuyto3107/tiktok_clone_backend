# features/user/schemas.py - Pydantic schemas for Firebase users
from typing import Optional
from pydantic import BaseModel


class FirebaseUserResponse(BaseModel):
    """Schema representing a single Firebase user account."""
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    phone_number: Optional[str] = None
    email_verified: bool = False
    disabled: bool = False
    provider_id: Optional[str] = None
    providers: list[str] = []
    creation_timestamp: Optional[int] = None  # ms since epoch
    last_sign_in_timestamp: Optional[int] = None  # ms since epoch


class FirebaseUserListResponse(BaseModel):
    """Response containing a list of all Firebase users."""
    users: list[FirebaseUserResponse]
    total: int
