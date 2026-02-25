"""fix_user_id_type

Revision ID: 549dc8697a5f
Revises: 6a5cb14cbecd
Create Date: 2026-02-25 12:10:39.962648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '549dc8697a5f'
down_revision: Union[str, None] = '6a5cb14cbecd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('posts', 'user_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.String(length=255),
                    existing_nullable=False)


def downgrade() -> None:
    pass