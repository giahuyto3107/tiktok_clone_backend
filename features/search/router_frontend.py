import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from features.post.models import Post, PostType
from features.post.router import _enrich_post, resolve_author
from features.post.service import PostService
from features.social.follow.models import Follow
from features.user.models import User, UserProfile
from .router import _search_users_db, _filter_users_by_query_firebase, _upsert_user_profiles
from .frontend_schemas import (
    DiscoverItem,
    DiscoverResponse,
    FrontendSearchResponse,
    FrontendUserItem,
    FrontendVideoResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_epoch_ms(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _safe_handle(name: str, fallback: str) -> str:
    base = (name or "").strip()
    if not base:
        base = fallback
    base = base.lower()
    base = re.sub(r"\s+", "", base)
    base = re.sub(r"[^a-z0-9._]", "", base)
    if not base:
        base = fallback
    if not base.startswith("@"):
        base = "@" + base
    return base


async def _users_to_frontend_items(
    db: AsyncSession,
    users: list,
) -> list[FrontendUserItem]:
    """
    Map UserProfile cache rows to Android `UserItem` with followerCount/totalLikes.
    """
    if not users:
        return []

    raw_uids = [u.uid for u in users]
    uid_map: dict[str, str] = {}
    if raw_uids:
        normalized_result = await db.execute(
            select(User.id, User.firebase_uid).where(
                (User.id.in_(raw_uids)) | (User.firebase_uid.in_(raw_uids))
            )
        )
        for user_id, firebase_uid in normalized_result.all():
            uid_map[user_id] = firebase_uid
            uid_map[firebase_uid] = firebase_uid

    uids = [uid_map.get(uid, uid) for uid in raw_uids]

    follower_rows = await db.execute(
        select(Follow.followee_id, func.count(Follow.follower_id))
        .where(Follow.followee_id.in_(uids))
        .group_by(Follow.followee_id)
    )
    follower_map = {uid: int(cnt) for uid, cnt in follower_rows.all()}

    likes_rows = await db.execute(
        select(Post.user_id, func.coalesce(func.sum(Post.like_count), 0))
        .where(Post.user_id.in_(uids))
        .group_by(Post.user_id)
    )
    likes_map = {uid: int(total) for uid, total in likes_rows.all()}

    out: list[FrontendUserItem] = []
    for idx, u in enumerate(users, start=1):
        normalized_uid = uid_map.get(u.uid, u.uid)
        display = u.username or u.email or normalized_uid[:8]
        out.append(
            FrontendUserItem(
                id=idx,
                uid=normalized_uid,
                display_name=display,
                handle=_safe_handle(display, normalized_uid[:8]),
                avatar=u.avatar or "",
                follower_count=follower_map.get(normalized_uid, 0),
                total_likes=likes_map.get(normalized_uid, 0),
                is_followed=False,
            )
        )
    return out


def _post_to_frontend_video(
    post,
    request: Request,
    profile_map: dict[str, UserProfile],
) -> FrontendVideoResult:
    """
    Build Android `VideoResult`.
    Prefer DB cache (`user_profiles`) for author fields; fallback to Firebase only if missing.
    """
    enriched = _enrich_post(post, request)
    thumb = enriched.thumbnail_url or enriched.media_url or ""

    author_name = "user"
    author_avatar = ""
    prof = profile_map.get(getattr(post, "user_id", "") or "")
    if prof is not None:
        author_name = prof.username or prof.email or prof.uid or "user"
        author_avatar = prof.avatar or ""
    else:
        # Fallback to Firebase for backward-compat / cache misses
        fb = resolve_author(getattr(post, "user_id", "") or "")
        if fb:
            author_name = fb.display_name or fb.uid or "user"
            author_avatar = fb.avatar_url or ""

    return FrontendVideoResult(
        id=int(enriched.id),
        thumbnail=thumb,
        title=enriched.caption or "",
        author=author_name,
        likes=int(getattr(post, "like_count", 0) or 0),
        author_avatar=author_avatar,
        created_at=_to_epoch_ms(getattr(post, "created_at", None)),
        duration_seconds=int(getattr(post, "duration", 0) or 0),
    )


@router.get("/discover", response_model=DiscoverResponse)
async def discover(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Android expects `DiscoverResponse(items=[{keyword,hot,previewThumb}])`.
    We generate it from recent posts + a thumbnail preview.
    """
    stmt = (
        select(Post)
        .where(Post.status == "READY")
        .order_by(Post.created_at.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()

    items: list[DiscoverItem] = []
    seen: set[str] = set()
    for p in posts:
        kw = (p.caption or "").strip()
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        enriched = _enrich_post(p, request)
        preview = enriched.thumbnail_url or enriched.media_url or None
        items.append(DiscoverItem(keyword=kw[:80], hot=True, preview_thumb=preview))
        if len(items) >= 10:
            break

    return DiscoverResponse(items=items)


@router.get("", response_model=FrontendSearchResponse)
async def search_all_frontend(
    request: Request,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    posts, _ = await PostService.search_posts(db, q, skip=0, limit=50)
    uids = list({p.user_id for p in posts if getattr(p, "user_id", None)})
    prof_map: dict[str, UserProfile] = {}
    if uids:
        profs_result = await db.execute(select(UserProfile).where(UserProfile.uid.in_(uids)))
        profs = profs_result.scalars().all()
        prof_map = {p.uid: p for p in profs}
    videos: list[FrontendVideoResult] = []
    images: list[str] = []
    for post in posts:
        if post.type == PostType.VIDEO:
            videos.append(_post_to_frontend_video(post, request, prof_map))
        else:
            enriched = _enrich_post(post, request)
            url = enriched.thumbnail_url or enriched.media_url or ""
            if url:
                images.append(url)

    # --- Build user list for "Người dùng" tab ---
    user_items: list[FrontendUserItem] = []

    # 1) Users that explicitly match the query (search bar "user search")
    cached = await _search_users_db(db, q, skip=0, limit=30)
    if cached:
        cached_uids = [u.uid for u in cached]
        profs_result = await db.execute(
            select(UserProfile).where(UserProfile.uid.in_(cached_uids))
        )
        profs = profs_result.scalars().all()
        user_items.extend(await _users_to_frontend_items(db, list(profs)))
    else:
        fb = _filter_users_by_query_firebase(q, max_results=30)
        try:
            await _upsert_user_profiles(db, fb)
        except Exception as e:
            logger.warning("User profile cache upsert failed: %s", e)
        user_items.extend(
            FrontendUserItem(
                id=len(user_items) + i + 1,
                uid=u.uid,
                display_name=u.username,
                handle=_safe_handle(u.username, u.uid[:8]),
                avatar=u.avatar,
                follower_count=0,
                total_likes=0,
                is_followed=False,
            )
            for i, u in enumerate(fb)
        )

    # 2) Always include authors of the matched posts (e.g. "minhpro" from review video)
    author_uids = list({p.user_id for p in posts if getattr(p, "user_id", None)})
    remaining_uids = [uid for uid in author_uids if uid not in {u.handle.lstrip("@") for u in user_items}]
    if remaining_uids:
        author_profs_result = await db.execute(
            select(UserProfile).where(UserProfile.uid.in_(remaining_uids))
        )
        author_profs = author_profs_result.scalars().all()
        author_items = await _users_to_frontend_items(db, list(author_profs))

        # Merge, preserving existing IDs and de-duplicating by handle
        existing_handles = {u.handle for u in user_items}
        for ai in author_items:
            if ai.handle in existing_handles:
                continue
            ai.id = len(user_items) + 1
            user_items.append(ai)
            existing_handles.add(ai.handle)

    return FrontendSearchResponse(
        videos=videos,
        users=user_items,
        products=[],
        images=images,
        lives=[],
    )


@router.get("/suggest", response_model=list[str])
async def suggest_frontend(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    # Reuse the existing suggest behavior from /api/v1/search
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

    cached = await _search_users_db(db, q, skip=0, limit=10)
    if not cached:
        cached = _filter_users_by_query_firebase(q, max_results=10)
        try:
            await _upsert_user_profiles(db, cached)
        except Exception as e:
            logger.warning("User profile cache upsert failed: %s", e)
    for u in cached:
        add_suggestion(u.username)

    return suggestions[:12]


@router.get("/videos", response_model=list[FrontendVideoResult])
async def search_videos_frontend(
    request: Request,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    posts, _ = await PostService.search_posts(db, q, skip=0, limit=50, post_type=PostType.VIDEO)
    uids = list({p.user_id for p in posts if getattr(p, "user_id", None)})
    prof_map: dict[str, UserProfile] = {}
    if uids:
        profs_result = await db.execute(select(UserProfile).where(UserProfile.uid.in_(uids)))
        profs = profs_result.scalars().all()
        prof_map = {p.uid: p for p in profs}
    return [_post_to_frontend_video(p, request, prof_map) for p in posts]


@router.get("/users", response_model=list[FrontendUserItem])
async def search_users_frontend(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    cached = await _search_users_db(db, q, skip=0, limit=30)
    if cached:
        profs_result = await db.execute(
            select(UserProfile).where(UserProfile.uid.in_([u.uid for u in cached]))
        )
        profs = profs_result.scalars().all()
        return await _users_to_frontend_items(db, list(profs))

    fb = _filter_users_by_query_firebase(q, max_results=30)
    try:
        await _upsert_user_profiles(db, fb)
    except Exception as e:
        logger.warning("User profile cache upsert failed: %s", e)
    return [
        FrontendUserItem(
            id=i + 1,
            uid=u.uid,
            display_name=u.username,
            handle=_safe_handle(u.username, u.uid[:8]),
            avatar=u.avatar,
            follower_count=0,
            total_likes=0,
            is_followed=False,
        )
        for i, u in enumerate(fb)
    ]


@router.get("/products", response_model=list)
async def search_products_frontend(
    q: str = Query(..., min_length=1),
):
    return []


@router.get("/live", response_model=list[FrontendVideoResult])
async def search_live_frontend(
    request: Request,
    q: str | None = Query(default=None),
):
    # No live feature in backend yet; return empty list to satisfy frontend contract.
    return []

