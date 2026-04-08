# database.py - MySQL Async Connection
import os
from collections.abc import AsyncGenerator
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# Build DATABASE_URL from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "tiktok_clone")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    # Ensure all model modules are imported so Base.metadata is fully populated.
    # Routers/services may not import every model module (e.g. user profile cache).
    from features.post import models as _post_models  # noqa: F401
    from features.inbox import models as _inbox_models  # noqa: F401
    from features.social.follow import models as _follow_models  # noqa: F401
    from features.social.follow_notification import models as _follow_notif_models  # noqa: F401
    from features.social.comment import models as _comment_models  # noqa: F401
    from features.social.reaction import models as _reaction_models  # noqa: F401
    from features.social.notification import models as _notif_models  # noqa: F401
    from features.social.share import models as _share_models  # noqa: F401
    from features.user import models as _user_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_schema_updates)


def _ensure_schema_updates(sync_conn) -> None:
    """
    Lightweight schema update for existing DBs.
    - Add comments.image_url if missing (for image comments).
    """
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "comments" not in tables:
        return

    comment_columns = {col["name"] for col in inspector.get_columns("comments")}
    if "image_url" not in comment_columns:
        sync_conn.execute(text("ALTER TABLE comments ADD COLUMN image_url VARCHAR(512) NULL"))
