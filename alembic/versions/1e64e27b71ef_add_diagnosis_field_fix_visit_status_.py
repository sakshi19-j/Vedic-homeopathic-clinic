"""add diagnosis field, fix visit_status enum, add ayurvedic type

Revision ID: 1e64e27b71ef
Revises: b8195d2dbc7f
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

revision = '1e64e27b71ef'
down_revision = 'b8195d2dbc7f'
branch_labels = None
depends_on = None


def upgrade():

    # ── Step 1: Create the enum types in Postgres FIRST ──────────
    visitstatus_enum = sa.Enum(
        'DRAFT', 'ACTIVE', 'BILLING', 'COMPLETED', 'CANCELLED',
        name='visitstatus'
    )
    visitstatus_enum.create(op.get_bind(), checkfirst=True)

    visittype_enum = sa.Enum(
        'ALLOPATHY', 'HOMEOPATHY', 'AYURVEDIC',
        name='visittype'
    )
    visittype_enum.create(op.get_bind(), checkfirst=True)

    # ── Step 2: Add diagnosis column ─────────────────────────────
    op.add_column(
        'visits',
        sa.Column('diagnosis', sa.String(), nullable=True)
    )

    # ── Step 3: Cast existing visit_status values + change type ──
    op.execute("""
        ALTER TABLE visits
        ALTER COLUMN visit_status
        TYPE visitstatus
        USING visit_status::visitstatus
    """)

    # ── Step 4: Set NOT NULL default ─────────────────────────────
    op.execute("""
        UPDATE visits
        SET visit_status = 'DRAFT'
        WHERE visit_status IS NULL
    """)

    op.alter_column(
        'visits', 'visit_status',
        nullable=False
    )

    # ── Step 5: Add AYURVEDIC to visittype enum if not exists ─────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'AYURVEDIC'
                AND enumtypid = 'visittype'::regtype
            ) THEN
                ALTER TYPE visittype ADD VALUE 'AYURVEDIC';
            END IF;
        END$$;
    """)


def downgrade():

    # Revert visit_status back to VARCHAR
    op.alter_column(
        'visits', 'visit_status',
        type_=sa.String(),
        existing_type=sa.Enum(
            'DRAFT', 'ACTIVE', 'BILLING', 'COMPLETED', 'CANCELLED',
            name='visitstatus'
        ),
        postgresql_using='visit_status::varchar',
        nullable=True
    )

    # Drop diagnosis column
    op.drop_column('visits', 'diagnosis')

    # Drop the enum type
    sa.Enum(name='visitstatus').drop(op.get_bind(), checkfirst=True)