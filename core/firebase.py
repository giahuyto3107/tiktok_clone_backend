# core/firebase.py - Firebase Admin SDK Initialization
import os
import firebase_admin
from firebase_admin import credentials

# Path to the service account key JSON file
_FIREBASE_CREDENTIALS_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_KEY",
    "firebase-service-account.json",
)

def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def init_firebase() -> bool:
    """
    Initialize the Firebase Admin SDK using a service account key.
    Call this once at application startup (e.g. in the FastAPI lifespan).
    """
    if firebase_admin._apps:
        # Already initialized — skip
        return True

    if not os.path.isfile(_FIREBASE_CREDENTIALS_PATH):
        # Default behavior: don't crash local dev if the key isn't present.
        # Set FIREBASE_REQUIRED=true to enforce this check (recommended for prod).
        if _env_flag("FIREBASE_REQUIRED", default=False):
            raise FileNotFoundError(
                f"Firebase service account key not found at: {_FIREBASE_CREDENTIALS_PATH}\n"
                "Download it from Firebase Console → Project Settings → Service Accounts."
            )
        print(
            f"⚠️  Firebase not initialized (missing service account at: {_FIREBASE_CREDENTIALS_PATH}). "
            "Set FIREBASE_SERVICE_ACCOUNT_KEY or provide the JSON file; "
            "or set FIREBASE_REQUIRED=true to fail fast."
        )
        return False

    cred = credentials.Certificate(_FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    print("[OK] Firebase Admin SDK initialized")
    return True
