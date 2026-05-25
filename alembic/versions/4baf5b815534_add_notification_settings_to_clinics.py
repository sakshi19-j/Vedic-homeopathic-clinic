"""add notification_settings to clinics

Revision ID: 4baf5b815534
Revises: e1f79d7227e8
Create Date: 2026-05-25 12:10:51.012909

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '4baf5b815534'
down_revision: Union[str, Sequence[str], None] = 'e1f79d7227e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =====================================================
# UPGRADE
# =====================================================

def upgrade() -> None:
    """
    Add notification_settings column safely
    only if it does not already exist.
    """

    conn = op.get_bind()

    result = conn.execute(
        text(
            "SELECT column_name "
            "FROM information_schema.columns "
            "WHERE table_name='clinics' "
            "AND column_name='notification_settings'"
        )
    )

    if not result.fetchone():

        op.add_column(
            "clinics",
            sa.Column(
                "notification_settings",
                sa.Text(),
                nullable=True
            )
        )


# =====================================================
# DOWNGRADE
# =====================================================

def downgrade() -> None:
    """
    Remove notification_settings column
    """

    op.drop_column(
        "clinics",
        "notification_settings"
    )