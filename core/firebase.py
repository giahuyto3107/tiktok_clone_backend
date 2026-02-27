# core/firebase.py - Firebase Admin SDK Initialization
import os
import firebase_admin
from firebase_admin import credentials

# Path to the service account key JSON file
_FIREBASE_CREDENTIALS_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_KEY",
    "firebase-service-account.json",
)


def init_firebase():
    """
    Initialize the Firebase Admin SDK using a service account key.
    Call this once at application startup (e.g. in the FastAPI lifespan).
    """
    if firebase_admin._apps:
        # Already initialized — skip
        return

    if not os.path.isfile(_FIREBASE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Firebase service account key not found at: {_FIREBASE_CREDENTIALS_PATH}\n"
            "Download it from Firebase Console → Project Settings → Service Accounts."
        )

    cred = credentials.Certificate(_FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized")
