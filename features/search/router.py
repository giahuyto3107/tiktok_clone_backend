import logging

from fastapi import APIRouter, Depends, Query, Request
from firebase_admin import auth as firebase_auth
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from features.post.models import PostType
from features.post.router import _enrich_post, resolve_author
from features.post.service import PostService
from features.user.models import UserProfile
from .schemas import SearchResponse, SearchUserItem, SearchVideoItem

logger = logging.getLogger(__name__)

router = APIRouter()


def _post_to_video_item(
    post,
    request: Request,
    profile_map: dict[str, UserProfile],
) -> SearchVideoItem:
    enriched = _enrich_post(post, request)
    thumb = enriched.thumbnail_url or enriched.media_url or ""
    author = "user"
    prof = profile_map.get(getattr(post, "user_id", "") or "")
    if prof is not None:
        author = prof.username or prof.email or prof.uid or "user"
    else:
        fb = resolve_author(getattr(post, "user_id", "") or "")
        if fb:
            author = fb.display_name or fb.uid or "user"
    # ORM still attached on enriched path — read like_count from original post
    likes = int(getattr(post, "like_count", 0) or 0)
    return SearchVideoItem(
        id=enriched.id,
        thumbnail=thumb,
        title=enriched.caption or "",
        author=author,
        likes=likes,
    )


def _escape_like_pattern(raw: str) -> str:
    return (
        (raw or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


async def _search_users_db(
    db: AsyncSession,
    q: str,
    skip: int,
    limit: int,
) -> list[SearchUserItem]:
    q = (q or "").strip()
    if not q:
        return []
    pattern = f"%{_escape_like_pattern(q)}%"
    stmt = (
        select(UserProfile)
        .where(
            or_(
                UserProfile.username.ilike(pattern, escape="\\"),
                UserProfile.email.ilike(pattern, escape="\\"),
                UserProfile.uid.ilike(pattern, escape="\\"),
            )
        )
        .order_by(UserProfile.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        SearchUserItem(
            uid=r.uid,
            username=r.username or r.email or r.uid[:8],
            avatar=r.avatar or "",
        )
        for r in rows
    ]


async def _upsert_user_profiles(
    db: AsyncSession,
    users: list[SearchUserItem],
) -> None:
    if not users:
        return
    for u in users:
        existing = await db.get(UserProfile, u.uid)
        if existing is None:
            db.add(
                UserProfile(
                    uid=u.uid,
                    username=u.username or "",
                    avatar=u.avatar or None,
                )
            )
        else:
            # keep it lightweight; only update fields we have
            existing.username = u.username or existing.username
            existing.avatar = u.avatar or existing.avatar
    await db.commit()


def _filter_users_by_query_firebase(
    q: str,
    max_results: int = 30,
) -> list[SearchUserItem]:
    q_lower = q.strip().lower()
    if not q_lower:
        return []
    out: list[SearchUserItem] = []
    try:
        page = firebase_auth.list_users(max_results=1000)
        while page:
            for u in page.users:
                if len(out) >= max_results:
                    return out
                name = (u.display_name or "").lower()
                email = (u.email or "").lower()
                if q_lower in name or q_lower in email or q_lower in u.uid.lower():
                    out.append(
                        SearchUserItem(
                            uid=u.uid,
                            username=u.display_name or u.email or u.uid[:8],
                            avatar=u.photo_url or "",
                        )
                    )
            page = page.get_next_page()
    except Exception as e:
        logger.warning("User search fallback (Firebase) skipped: %s", e)
    return out


@router.get("", response_model=SearchResponse)
async def search_all(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    posts, _ = await PostService.search_posts(db, q, skip=skip, limit=limit)
    uids = list({p.user_id for p in posts if getattr(p, "user_id", None)})
    prof_map: dict[str, UserProfile] = {}
    if uids:
        profs_result = await db.execute(select(UserProfile).where(UserProfile.uid.in_(uids)))
        profs = profs_result.scalars().all()
        prof_map = {p.uid: p for p in profs}
    videos: list[SearchVideoItem] = []
    images: list[str] = []
    for post in posts:
        if post.type == PostType.VIDEO:
            videos.append(_post_to_video_item(post, request, prof_map))
        else:
            enriched = _enrich_post(post, request)
            url = enriched.thumbnail_url or enriched.media_url or ""
            if url:
                images.append(url)
    users = await _search_users_db(db, q, skip=0, limit=30)
    if not users:
        users = _filter_users_by_query_firebase(q, max_results=30)
        try:
            await _upsert_user_profiles(db, users)
        except Exception as e:
            logger.warning("User profile cache upsert failed: %s", e)
    return SearchResponse(videos=videos, users=users, products=[], images=images, lives=[])


@router.get("/suggest", response_model=list[str])
async def search_suggest(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Short suggestions: matching captions and user display names."""
    suggestions: list[str] = []
    seen: set[str] = set()

    def add_suggestion(s: str) -> None:
        t = s.strip()
        if len(t) < 2 or t.lower() in seen:
            return
        seen.add(t.lower())
        suggestions.append(t)

    posts, _ = await PostService.search_posts(db, q, skip=0, limit=15)
    for post in posts:
        cap = (post.caption or "").strip()
        if cap:
            add_suggestion(cap if len(cap) <= 80 else cap[:77] + "…")

    users = await _search_users_db(db, q, skip=0, limit=10)
    if not users:
        users = _filter_users_by_query_firebase(q, max_results=10)
        try:
            await _upsert_user_profiles(db, users)
        except Exception as e:
            logger.warning("User profile cache upsert failed: %s", e)
    for u in users:
        add_suggestion(u.username)

    return suggestions[:12]


@router.get("/videos", response_model=list[SearchVideoItem])
async def search_videos(
    request: Request,
    q: str = Query(..., min_length=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    posts, _ = await PostService.search_posts(
        db, q, skip=skip, limit=limit, post_type=PostType.VIDEO
    )
    uids = list({p.user_id for p in posts if getattr(p, "user_id", None)})
    prof_map: dict[str, UserProfile] = {}
    if uids:
        profs_result = await db.execute(select(UserProfile).where(UserProfile.uid.in_(uids)))
        profs = profs_result.scalars().all()
        prof_map = {p.uid: p for p in profs}
    return [_post_to_video_item(p, request, prof_map) for p in posts]


@router.get("/users", response_model=list[SearchUserItem])
async def search_users(
    q: str = Query(..., min_length=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    users = await _search_users_db(db, q, skip=skip, limit=limit)
    if users:
        return users
    users = _filter_users_by_query_firebase(q, max_results=min(limit, 100))
    try:
        await _upsert_user_profiles(db, users)
    except Exception as e:
        logger.warning("User profile cache upsert failed: %s", e)
    return users


@router.get("/products", response_model=list)
async def search_products():
    return []


@router.get("/live", response_model=list[str])
async def search_live():
    return []
