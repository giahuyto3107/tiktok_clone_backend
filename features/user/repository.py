# features/user/repository.py
from datetime import date
from typing import Optional, List, Tuple
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserStats, UserProfile

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        stmt = select(User).options(selectinload(User.stats)).where(User.firebase_uid == firebase_uid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).options(selectinload(User.stats)).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).options(selectinload(User.stats)).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        firebase_uid: str,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        username: Optional[str] = None,
    ) -> User:
        # Default username logic if not provided
        if not username:
            username = f"user_{firebase_uid[:8].lower()}"
            
        new_user = User(
            firebase_uid=firebase_uid,
            email=email,
            phone_number=phone_number,
            full_name=full_name,
            avatar_url=avatar_url,
            date_of_birth=date_of_birth,
            username=username
        )
        self.session.add(new_user)
        await self.session.flush() # flush to get internal ID to create stats
        
        # Create empty stats for user
        stats = UserStats(user_id=new_user.id)
        self.session.add(stats)
        
        await self.session.commit()
        await self.session.refresh(new_user)
        
        # Manually attach stats so it's loaded 
        new_user.stats = stats
        await self.upsert_user_profile(
            firebase_uid=new_user.firebase_uid,
            username=new_user.username,
            email=new_user.email,
            avatar_url=new_user.avatar_url,
        )
        return new_user

    async def create_user_admin(
        self,
        full_name: str,
        username: str,
        email: str,
        bio: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        """
        Tạo user trực tiếp từ Admin panel, không qua Firebase Auth.
        Sinh ra một firebase_uid giả có prefix 'admin_' để không bị
        xung đột với user đăng ký bình thường qua Firebase.
        Tự động tạo bản ghi UserStats rỗng cho user mới.
        """
        import uuid as uuid_module
        # Tạo firebase_uid giả — user này không thể đăng nhập qua Firebase
        fake_firebase_uid = f"admin_{str(uuid_module.uuid4()).replace('-', '')}"

        new_user = User(
            firebase_uid=fake_firebase_uid,
            email=email,
            full_name=full_name,
            username=username,
            bio=bio,
            avatar_url=avatar_url,
        )
        self.session.add(new_user)
        await self.session.flush()  # Flush để lấy new_user.id trước khi tạo stats

        # Tạo bảng thống kê rỗng (followers/following/likes = 0)
        stats = UserStats(user_id=new_user.id)
        self.session.add(stats)

        await self.session.commit()
        await self.session.refresh(new_user)
        new_user.stats = stats  # Gán thủ công vì lazy load chưa kịp thực thi
        await self.upsert_user_profile(
            firebase_uid=new_user.firebase_uid,
            username=new_user.username,
            email=new_user.email,
            avatar_url=new_user.avatar_url,
        )
        return new_user

    async def update_user(self, user: User, update_data: dict) -> User:
        """
        Cập nhật các field của user theo dict update_data.
        Chỉ ghi những field có giá trị khác None,
        tránh ghi đè dữ liệu cũ bằng None không mong muốn.
        """
        for key, value in update_data.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
                
        await self.session.commit()
        await self.session.refresh(user)
        await self.upsert_user_profile(
            firebase_uid=user.firebase_uid,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
        )
        return user
        
    async def get_users_paginated(self, page: int, limit: int) -> Tuple[List[User], int]:
        """Return paginated users and total count (for admin)"""
        offset = (page - 1) * limit
        
        # Count total
        count_stmt = select(func.count()).select_from(User)
        total_count = await self.session.scalar(count_stmt)
        
        # Fetch items
        stmt = select(User).options(selectinload(User.stats))\
            .order_by(User.created_at.desc())\
            .offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        users = result.scalars().all()
        
        return list(users), total_count or 0
        
    async def count_new_users_last_30_days(self) -> int:
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        stmt = select(func.count()).select_from(User).where(User.created_at >= thirty_days_ago)
        count = await self.session.scalar(stmt)
        return count or 0

    async def update_user_status(self, user_id: str, is_banned: Optional[bool] = None, is_verified: Optional[bool] = None) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
            
        if is_banned is not None:
            user.is_banned = is_banned
        if is_verified is not None:
            user.is_verified = is_verified
            
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def upsert_user_profile(
        self,
        firebase_uid: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> UserProfile:
        """
        Keep user_profiles.uid aligned with Firebase UID for search payloads.
        """
        profile = await self.session.get(UserProfile, firebase_uid)
        if profile is None:
            profile = UserProfile(
                uid=firebase_uid,
                username=username,
                email=email,
                avatar=avatar_url,
            )
            self.session.add(profile)
        else:
            profile.username = username if username is not None else profile.username
            profile.email = email if email is not None else profile.email
            profile.avatar = avatar_url if avatar_url is not None else profile.avatar

        await self.session.commit()
        await self.session.refresh(profile)
        return profile
