from fastapi import APIRouter

from .follow.router import router as follow_router
from .reaction.router import router as reaction_router
from .share.router import router as share_router
from .comment.router import router as comment_router
from .notification.router import router as notification_router
from .follow_notification.router import router as follow_notification_router

router = APIRouter()

router.include_router(follow_router)
router.include_router(reaction_router)
router.include_router(share_router)
router.include_router(comment_router)
router.include_router(notification_router)
router.include_router(follow_notification_router)

