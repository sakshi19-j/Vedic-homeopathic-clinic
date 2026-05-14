"""add staff_limit to clinics

Revision ID: e1f79d7227e8
Revises: 48b5f5ba4a9c
Create Date: 2026-05-14 10:30:14.113266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f79d7227e8'
down_revision: Union[str, Sequence[str], None] = '48b5f5ba4a9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Column already exists in DB — just ensure default is set
    op.execute(
        "UPDATE clinics SET staff_limit = 2 WHERE staff_limit IS NULL"
    )


def downgrade() -> None:
    pass