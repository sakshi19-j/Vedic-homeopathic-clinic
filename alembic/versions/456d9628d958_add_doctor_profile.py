"""add doctor profile

Revision ID: 456d9628d958
Revises: 4baf5b815534
Create Date: 2026-06-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "456d9628d958"
down_revision: Union[str, Sequence[str], None] = "4baf5b815534"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # add new columns
    op.add_column(
        "doctor_profiles",
        sa.Column(
            "clinic_id",
            sa.String(),
            nullable=True
        )
    )

    op.add_column(
        "doctor_profiles",
        sa.Column(
            "qualification",
            sa.String(),
            nullable=True
        )
    )

    op.add_column(
        "doctor_profiles",
        sa.Column(
            "clinic_address",
            sa.String(),
            nullable=True
        )
    )

    op.add_column(
        "doctor_profiles",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True
        )
    )

    # create index
    op.create_index(
        "ix_doctor_profiles_clinic_id",
        "doctor_profiles",
        ["clinic_id"],
        unique=False
    )


def downgrade() -> None:

    op.drop_index(
        "ix_doctor_profiles_clinic_id",
        table_name="doctor_profiles"
    )

    op.drop_column(
        "doctor_profiles",
        "updated_at"
    )

    op.drop_column(
        "doctor_profiles",
        "clinic_address"
    )

    op.drop_column(
        "doctor_profiles",
        "qualification"
    )

    op.drop_column(
        "doctor_profiles",
        "clinic_id"
    )
