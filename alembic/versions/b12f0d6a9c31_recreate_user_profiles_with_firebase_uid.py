"""recreate user_profiles with firebase uid

Revision ID: b12f0d6a9c31
Revises: 8c1b2f4d3e21
Create Date: 2026-04-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b12f0d6a9c31"
down_revision: Union[str, None] = "8c1b2f4d3e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recreate bảng để làm sạch dữ liệu cũ (uid nội bộ) và chuẩn hóa theo Firebase UID.
    op.execute("DROP TABLE IF EXISTS user_profiles")

    op.create_table(
        "user_profiles",
        sa.Column("uid", sa.String(length=128), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_index("ix_user_profiles_username", "user_profiles", ["username"])
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"])
    op.execute(
        "CREATE FULLTEXT INDEX ft_user_profiles_username_email ON user_profiles (username, email)"
    )

    # Backfill từ users: uid phải là firebase_uid để đồng nhất với các bảng social/post/follow.
    op.execute(
        """
        INSERT INTO user_profiles (uid, username, email, avatar, created_at, updated_at)
        SELECT
            u.firebase_uid,
            u.username,
            u.email,
            u.avatar_url,
            COALESCE(u.created_at, UTC_TIMESTAMP()),
            UTC_TIMESTAMP()
        FROM users u
        WHERE u.firebase_uid IS NOT NULL
          AND u.firebase_uid <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_profiles")
    op.create_table(
        "user_profiles",
        sa.Column("uid", sa.String(length=255), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_user_profiles_username", "user_profiles", ["username"])
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"])
    op.execute(
        "CREATE FULLTEXT INDEX ft_user_profiles_username_email ON user_profiles (username, email)"
    )
