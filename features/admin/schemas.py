# features/admin/schemas.py
# ─────────────────────────────────────────────────────────────────────────────
# Định nghĩa các Pydantic schema dùng cho Admin API:
#   - Response: dữ liệu trả về cho frontend
#   - Request:  body nhận từ frontend khi tạo / cập nhật / đổi trạng thái user
# ─────────────────────────────────────────────────────────────────────────────
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# ── Response schemas ───────────────────────────────────────────────────────

# Dữ liệu 3 card số liệu trên Dashboard
class AdminDashboardStats(BaseModel):
    total_users: int
    new_users: int      # Đăng ký trong 30 ngày gần nhất
    active_users: int   # Tổng - banned

# Đại diện cho một dòng trong bảng user (dùng chung cho list + tạo mới + sửa)
class AdminUserItem(BaseModel):
    id: str
    stt: str        # Số thứ tự dạng chuỗi, vd "01"
    name: str       # full_name
    handle: str     # @username
    email: str
    date: str       # created_at đã format dd/MM/yyyy
    avatarUrl: str
    bio: str
    followers: str  # Đã format: "1.2M", "5K", ...
    following: str
    likes: str
    isVerified: bool
    isBanned: bool

    class Config:
        from_attributes = True  # Cho phép tạo từ ORM object (SQLAlchemy)

# Wrapper phân trang trả về khi GET /admin/users
class AdminUserListResponse(BaseModel):
    items: List[AdminUserItem]
    total: int          # Tổng số user (để frontend tính số trang)
    page: int
    limit: int
    total_pages: int

# ── Request schemas ────────────────────────────────────────────────────────

# Body cho PUT /admin/users/{id}/status — ban hoặc verify user
# Chỉ truyền field cần thay đổi, field còn lại để None
class AdminUserUpdateStatusRequest(BaseModel):
    is_banned: Optional[bool] = None
    is_verified: Optional[bool] = None

# Body cho POST /admin/users — Admin tạo user mới (không qua Firebase)
class AdminCreateUserRequest(BaseModel):
    full_name: str
    username: str
    email: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

# Body cho PUT /admin/users/{id}/profile — Admin chỉnh sửa thông tin user
# Mọi field đều Optional: chỉ field có giá trị mới được ghi vào DB
class AdminUpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None

# ── Content Management schemas ─────────────────────────────────────────────

# Đại diện cho một bài post trong bảng Content Management
class AdminPostItem(BaseModel):
    id: str
    stt: str
    user_id: str
    username: str       # @username của tác giả
    caption: str
    type: str           # VIDEO hoặc IMAGE
    status: str         # PROCESSING / READY / FAILED
    thumbnail_url: str
    media_url: str
    like_count: int
    comment_count: int
    date: str           # created_at đã format dd/MM/yyyy

    class Config:
        from_attributes = True

# Wrapper phân trang cho GET /admin/posts
class AdminPostListResponse(BaseModel):
    items: List[AdminPostItem]
    total: int
    page: int
    limit: int
    total_pages: int
