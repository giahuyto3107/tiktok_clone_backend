"""add user_profiles and search indexes

Revision ID: 8c1b2f4d3e21
Revises: a5e35b922aba
Create Date: 2026-04-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c1b2f4d3e21"
down_revision: Union[str, None] = "a5e35b922aba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("uid", sa.String(length=255), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        mysql_engine="InnoDB",
        mysql_default_charset="utf8mb4",
    )

    op.create_index("ix_user_profiles_username", "user_profiles", ["username"])
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"])

    # FULLTEXT indexes (MySQL/InnoDB)
    op.execute(
        "CREATE FULLTEXT INDEX ft_user_profiles_username_email ON user_profiles (username, email)"
    )
    op.execute(
        "CREATE FULLTEXT INDEX ft_posts_caption_music ON posts (caption, music_name)"
    )

    # Useful sort/filter indexes for feeds & search
    op.create_index("ix_posts_created_at", "posts", ["created_at"])
    op.create_index("ix_posts_user_id_created_at", "posts", ["user_id", "created_at"])
    op.create_index(
        "ix_posts_type_status_created_at",
        "posts",
        ["type", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_posts_type_status_created_at", table_name="posts")
    op.drop_index("ix_posts_user_id_created_at", table_name="posts")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.execute("DROP INDEX ft_posts_caption_music ON posts")

    op.execute("DROP INDEX ft_user_profiles_username_email ON user_profiles")
    op.drop_index("ix_user_profiles_email", table_name="user_profiles")
    op.drop_index("ix_user_profiles_username", table_name="user_profiles")
    op.drop_table("user_profiles")

