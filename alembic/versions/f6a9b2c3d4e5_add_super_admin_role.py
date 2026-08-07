"""add super_admin to app_role enum

Revision ID: f6a9b2c3d4e5
Revises: e1f79d7227e8
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a9b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '684eeba0e433'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'super_admin'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
