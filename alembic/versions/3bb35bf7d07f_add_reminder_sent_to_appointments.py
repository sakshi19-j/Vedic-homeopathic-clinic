"""add reminder_sent to appointments

Revision ID: 3bb35bf7d07f
Revises: 57fb01e86a15
Create Date: 2026-05-11 12:50:26.463523

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3bb35bf7d07f'
down_revision: Union[str, Sequence[str], None] = '57fb01e86a15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1 — drop existing default first
    op.execute(
        "ALTER TABLE whatsapp_logs ALTER COLUMN delivery_status DROP DEFAULT"
    )

    # Step 2 — create enum type if not exists
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE deliverystatus AS ENUM (
            'SENT',
            'DELIVERED',
            'READ',
            'FAILED',
            'MOCKED'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END
    $$;
    """)

    # Step 3 — cast varchar column to enum
    op.execute("""
    ALTER TABLE whatsapp_logs
    ALTER COLUMN delivery_status
    TYPE deliverystatus
    USING delivery_status::deliverystatus
    """)

    # Step 4 — restore default
    op.execute(
        "ALTER TABLE whatsapp_logs ALTER COLUMN delivery_status SET DEFAULT 'SENT'"
    )

    # Remove old APScheduler table
    op.drop_index(
        op.f('ix_apscheduler_jobs_next_run_time'),
        table_name='apscheduler_jobs'
    )

    op.drop_table('apscheduler_jobs')

    # Add reminder_sent column
    op.add_column(
        'appointments',
        sa.Column('reminder_sent', sa.Boolean(), nullable=True)
    )

    # Follow-up index
    op.create_index(
        op.f('ix_follow_ups_clinic_id'),
        'follow_ups',
        ['clinic_id'],
        unique=False
    )

    # Remove old prescription_url
    op.drop_column('visits', 'prescription_url')

    # Fix nullable timestamps
    op.alter_column(
        'whatsapp_logs',
        'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
        existing_server_default=sa.text('now()')
    )

    op.alter_column(
        'whatsapp_logs',
        'updated_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
        existing_server_default=sa.text('now()')
    )

    # Drop old indexes
    op.drop_index(
        op.f('idx_whatsapp_logs_clinic'),
        table_name='whatsapp_logs'
    )

    op.drop_index(
        op.f('idx_whatsapp_logs_msg_id'),
        table_name='whatsapp_logs'
    )

    op.drop_index(
        op.f('idx_whatsapp_logs_patient'),
        table_name='whatsapp_logs'
    )

    # Create new indexes
    op.create_index(
        op.f('ix_whatsapp_logs_clinic_id'),
        'whatsapp_logs',
        ['clinic_id'],
        unique=False
    )

    op.create_index(
        op.f('ix_whatsapp_logs_message_id'),
        'whatsapp_logs',
        ['message_id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f('ix_whatsapp_logs_message_id'),
        table_name='whatsapp_logs'
    )

    op.drop_index(
        op.f('ix_whatsapp_logs_clinic_id'),
        table_name='whatsapp_logs'
    )

    op.create_index(
        op.f('idx_whatsapp_logs_patient'),
        'whatsapp_logs',
        ['patient_id'],
        unique=False
    )

    op.create_index(
        op.f('idx_whatsapp_logs_msg_id'),
        'whatsapp_logs',
        ['message_id'],
        unique=False
    )

    op.create_index(
        op.f('idx_whatsapp_logs_clinic'),
        'whatsapp_logs',
        ['clinic_id'],
        unique=False
    )

    op.alter_column(
        'whatsapp_logs',
        'updated_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
        existing_server_default=sa.text('now()')
    )

    op.alter_column(
        'whatsapp_logs',
        'created_at',
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
        existing_server_default=sa.text('now()')
    )

    op.alter_column(
        'whatsapp_logs',
        'delivery_status',
        existing_type=sa.Enum(
            'SENT',
            'DELIVERED',
            'READ',
            'FAILED',
            'MOCKED',
            name='deliverystatus'
        ),
        type_=sa.VARCHAR(),
        existing_nullable=True,
        existing_server_default=sa.text("'SENT'::character varying")
    )

    op.add_column(
        'visits',
        sa.Column(
            'prescription_url',
            sa.VARCHAR(),
            autoincrement=False,
            nullable=True
        )
    )

    op.drop_index(
        op.f('ix_follow_ups_clinic_id'),
        table_name='follow_ups'
    )

    op.drop_column('appointments', 'reminder_sent')

    op.create_table(
        'apscheduler_jobs',
        sa.Column(
            'id',
            sa.VARCHAR(length=191),
            autoincrement=False,
            nullable=False
        ),
        sa.Column(
            'next_run_time',
            sa.DOUBLE_PRECISION(precision=53),
            autoincrement=False,
            nullable=True
        ),
        sa.Column(
            'job_state',
            postgresql.BYTEA(),
            autoincrement=False,
            nullable=False
        ),
        sa.PrimaryKeyConstraint(
            'id',
            name=op.f('apscheduler_jobs_pkey')
        )
    )

    op.create_index(
        op.f('ix_apscheduler_jobs_next_run_time'),
        'apscheduler_jobs',
        ['next_run_time'],
        unique=False
    )