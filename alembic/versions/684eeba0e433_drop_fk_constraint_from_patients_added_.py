"""drop fk constraint from patients.added_by_staff_id

Revision ID: 684eeba0e433
Revises: 33dd0f197792
Create Date: 2026-08-06 16:44:38.792284

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '684eeba0e433'
down_revision: Union[str, Sequence[str], None] = '33dd0f197792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'patients'
                  AND kcu.column_name = 'added_by_staff_id'
            ) THEN
                ALTER TABLE patients DROP CONSTRAINT patients_added_by_staff_id_fkey;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
