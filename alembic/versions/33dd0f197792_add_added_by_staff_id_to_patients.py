"""add added_by_staff_id to patients

Revision ID: 33dd0f197792
Revises: 456d9628d958
Create Date: 2026-08-06 08:20:44.912214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33dd0f197792'
down_revision: Union[str, Sequence[str], None] = '456d9628d958'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'patients',
        sa.Column('added_by_staff_id', sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('patients', 'added_by_staff_id')
