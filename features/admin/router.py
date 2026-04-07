# features/admin/router.py
# ─────────────────────────────────────────────────────────────────────────────
# Định nghĩa tất cả endpoint REST của Admin panel.
# Router này được mount tại /api/v1/admin/ trong main.py.
#
# Danh sách endpoint:
#   GET    /dashboard/stats          → Số liệu tổng quan Dashboard
#   GET    /users                    → Danh sách user có phân trang
#   PUT    /users/{id}/status        → Ban / verify user
#   POST   /users                    → Tạo user mới từ Admin panel
#   PUT    /users/{id}/profile       → Chỉnh sửa thông tin profile user
#   GET    /posts                    → Danh sách bài post có phân trang
#   DELETE /posts/{id}               → Xóa bài post
# ─────────────────────────────────────────────────────────────────────────────
import logging
import math
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from features.user.models import User, UserStats
from features.user.repository import UserRepository
from features.post.models import Post, PostType
from .schemas import (
    AdminDashboardStats, AdminUserListResponse, AdminUserItem,
    AdminUserUpdateStatusRequest, AdminCreateUserRequest, AdminUpdateUserRequest,
    AdminPostItem, AdminPostListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()

def _format_number(n: int) -> str:
    """Helper to format large numbers like 1.2M, 5K etc."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    elif n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)

@router.get("/dashboard/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get high-level statistics for Admin Dashboard."""
    try:
        user_repo = UserRepository(db)
        
        # Total users
        total_stmt = select(func.count()).select_from(User)
        total_users = await db.scalar(total_stmt) or 0
        
        # New users in 30 days
        new_users = await user_repo.count_new_users_last_30_days()
        
        # Active users (for MVP: total - banned)
        banned_stmt = select(func.count()).select_from(User).where(User.is_banned == True)
        banned_users = await db.scalar(banned_stmt) or 0
        active_users = total_users - banned_users
        
        return AdminDashboardStats(
            total_users=total_users,
            new_users=new_users,
            active_users=active_users
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch dashboard stats")


@router.get("/users", response_model=AdminUserListResponse)
async def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of users mapped to FE AdminUser format."""
    try:
        user_repo = UserRepository(db)
        users, total_count = await user_repo.get_users_paginated(page, limit)
        
        items = []
        for i, u in enumerate(users):
            stats = u.stats
            
            # Map DB user to AdminUserItem
            item = AdminUserItem(
                id=u.id,
                stt=f"{(page - 1) * limit + i + 1:02d}", # e.g. "01", "02"
                name=u.full_name or "Unknown User",
                handle=f"@{u.username}" if u.username else "@user",
                email=u.email or "No email",
                date=u.created_at.strftime("%d/%m/%Y"),
                avatarUrl=u.avatar_url or "",
                bio=u.bio or "No bio provided.",
                followers=_format_number(stats.followers_count if stats else 0),
                following=_format_number(stats.following_count if stats else 0),
                likes=_format_number(stats.likes_count if stats else 0),
                isVerified=u.is_verified,
                isBanned=u.is_banned
            )
            items.append(item)
            
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        
        return AdminUserListResponse(
            items=items,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch users list")


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    request: AdminUserUpdateStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify or ban a user from the Admin panel."""
    user_repo = UserRepository(db)
    updated_user = await user_repo.update_user_status(
        user_id=user_id,
        is_banned=request.is_banned,
        is_verified=request.is_verified
    )
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": "User status updated successfully", "user_id": updated_user.id}


@router.post("/users", response_model=AdminUserItem, status_code=201)
async def create_admin_user(
    request: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user directly from the Admin panel."""
    try:
        user_repo = UserRepository(db)

        existing = await user_repo.get_by_username(request.username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        new_user = await user_repo.create_user_admin(
            full_name=request.full_name,
            username=request.username,
            email=request.email,
            bio=request.bio,
            avatar_url=request.avatar_url,
        )
        stats = new_user.stats
        return AdminUserItem(
            id=new_user.id,
            stt="--",
            name=new_user.full_name or "Unknown User",
            handle=f"@{new_user.username}" if new_user.username else "@user",
            email=new_user.email or "No email",
            date=new_user.created_at.strftime("%d/%m/%Y"),
            avatarUrl=new_user.avatar_url or "",
            bio=new_user.bio or "",
            followers="0",
            following="0",
            likes="0",
            isVerified=new_user.is_verified,
            isBanned=new_user.is_banned,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Could not create user")


@router.put("/users/{user_id}/profile", response_model=AdminUserItem)
async def update_admin_user_profile(
    user_id: str,
    request: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Edit user profile info from the Admin panel."""
    try:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = {}
        if request.full_name is not None:
            update_data["full_name"] = request.full_name
        if request.username is not None:
            update_data["username"] = request.username
        if request.email is not None:
            update_data["email"] = request.email
        if request.bio is not None:
            update_data["bio"] = request.bio
        if request.avatar_url is not None:
            update_data["avatar_url"] = request.avatar_url

        updated = await user_repo.update_user(user, update_data)
        stats = updated.stats
        return AdminUserItem(
            id=updated.id,
            stt="--",
            name=updated.full_name or "Unknown User",
            handle=f"@{updated.username}" if updated.username else "@user",
            email=updated.email or "No email",
            date=updated.created_at.strftime("%d/%m/%Y"),
            avatarUrl=updated.avatar_url or "",
            bio=updated.bio or "",
            followers=_format_number(stats.followers_count if stats else 0),
            following=_format_number(stats.following_count if stats else 0),
            likes=_format_number(stats.likes_count if stats else 0),
            isVerified=updated.is_verified,
            isBanned=updated.is_banned,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail="Could not update user profile")


# ── Content Management endpoints ────────────────────────────────────────────

@router.get("/posts", response_model=AdminPostListResponse)
async def get_admin_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    post_type: str = Query(None, alias="type"),  # VIDEO / IMAGE / None
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of all posts for Content Management."""
    try:
        offset = (page - 1) * limit

        # Base query: join Post with User to get username
        base_stmt = select(Post, User).join(User, Post.user_id == User.id, isouter=True)
        if post_type in ("VIDEO", "IMAGE"):
            base_stmt = base_stmt.where(Post.type == post_type)

        # Count total
        count_subq = base_stmt.subquery()
        count_stmt = select(func.count()).select_from(count_subq)
        total_count = await db.scalar(count_stmt) or 0

        # Paginated rows ordered by newest first
        rows_stmt = base_stmt.order_by(Post.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(rows_stmt)
        rows = result.all()

        items = []
        for i, row in enumerate(rows):
            post = row[0]
            user = row[1]
            items.append(AdminPostItem(
                id=str(post.id),
                stt=f"{(page - 1) * limit + i + 1:02d}",
                user_id=str(post.user_id),
                username=f"@{user.username}" if user and user.username else "@unknown",
                caption=post.caption or "",
                type=post.type.value,
                status=post.status.value,
                thumbnail_url=post.thumbnail_url or "",
                media_url=post.media_url or "",
                like_count=post.like_count,
                comment_count=post.comment_count,
                date=post.created_at.strftime("%d/%m/%Y")
            ))

        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
        return AdminPostListResponse(
            items=items,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error fetching posts: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch posts")


@router.delete("/posts/{post_id}", status_code=200)
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a post permanently from the Admin panel."""
    try:
        stmt = select(Post).where(Post.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        await db.delete(post)
        await db.commit()
        return {"message": "Post deleted successfully", "post_id": post_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete post")
