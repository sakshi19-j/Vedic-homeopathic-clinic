"""merge migration heads

Revision ID: 48b5f5ba4a9c
Revises: a1b2c3d4e5f6, c0e5d7506884
Create Date: 2026-05-14 10:29:54.319678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48b5f5ba4a9c'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'c0e5d7506884')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
