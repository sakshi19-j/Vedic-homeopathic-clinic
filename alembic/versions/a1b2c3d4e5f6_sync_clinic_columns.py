"""sync clinic columns — add all missing fields

Revision ID: a1b2c3d4e5f6
Revises: 689f53bca871
Create Date: 2026-05-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '689f53bca871'
branch_labels = None
depends_on = None


def column_exists(table: str, column: str) -> bool:
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
    """), {"t": table, "c": column})
    return result.scalar() > 0


def add_if_missing(table: str, column: str, col_def):
    if not column_exists(table, column):
        op.add_column(table, sa.Column(column, col_def))
        print(f"  ✅ Added {table}.{column}")
    else:
        print(f"  ⏭  Skipped {table}.{column} — already exists")


def upgrade() -> None:
    print("\n🔧 Syncing clinic columns...\n")

    # ── Subscription fields ───────────────────────
    add_if_missing("clinics", "subscription_plan",
        sa.String(), )
    add_if_missing("clinics", "subscription_period",
        sa.String())
    add_if_missing("clinics", "razorpay_subscription_id",
        sa.String())
    add_if_missing("clinics", "subscription_start_date",
        sa.DateTime())

    # ── Plan limits ───────────────────────────────
    add_if_missing("clinics", "max_patients_per_month",
        sa.Integer())
    add_if_missing("clinics", "max_staff",
        sa.Integer())
    add_if_missing("clinics", "max_doctors",
        sa.Integer())
    add_if_missing("clinics", "staff_limit",
        sa.Integer())

    # ── Branding ──────────────────────────────────
    add_if_missing("clinics", "branding_enabled",
        sa.Boolean())
    add_if_missing("clinics", "custom_logo",
        sa.String())
    add_if_missing("clinics", "primary_color",
        sa.String())
    add_if_missing("clinics", "secondary_color",
        sa.String())

    # ── Onboarding flags ──────────────────────────
    add_if_missing("clinics", "onboarding_complete",
        sa.Boolean())
    add_if_missing("clinics", "has_logo",
        sa.Boolean())
    add_if_missing("clinics", "has_signature",
        sa.Boolean())
    add_if_missing("clinics", "has_whatsapp",
        sa.Boolean())
    add_if_missing("clinics", "has_first_patient",
        sa.Boolean())
    add_if_missing("clinics", "has_first_consultation",
        sa.Boolean())
    add_if_missing("clinics", "onboarding_dismissed",
        sa.Boolean())

    # ── Settings ──────────────────────────────────
    add_if_missing("clinics", "is_active",
        sa.Boolean())

    # ── Set defaults for existing rows ────────────
    op.execute("""
        UPDATE clinics SET
            max_patients_per_month  = COALESCE(max_patients_per_month, 100),
            max_staff               = COALESCE(max_staff, 0),
            max_doctors             = COALESCE(max_doctors, 1),
            staff_limit             = COALESCE(staff_limit, 2),
            branding_enabled        = COALESCE(branding_enabled, false),
            primary_color           = COALESCE(primary_color, '#16a34a'),
            secondary_color         = COALESCE(secondary_color, '#2563eb'),
            onboarding_complete     = COALESCE(onboarding_complete, false),
            has_logo                = COALESCE(has_logo, false),
            has_signature           = COALESCE(has_signature, false),
            has_whatsapp            = COALESCE(has_whatsapp, false),
            has_first_patient       = COALESCE(has_first_patient, false),
            has_first_consultation  = COALESCE(has_first_consultation, false),
            onboarding_dismissed    = COALESCE(onboarding_dismissed, false),
            is_active               = COALESCE(is_active, true)
    """)

    print("\n✅ Clinic columns synced successfully\n")


def downgrade() -> None:
    # Safe to run — only removes columns added in this migration
    cols = [
        "subscription_plan", "subscription_period",
        "razorpay_subscription_id", "subscription_start_date",
        "max_patients_per_month", "max_staff", "max_doctors", "staff_limit",
        "branding_enabled", "custom_logo", "primary_color", "secondary_color",
        "onboarding_complete", "has_logo", "has_signature", "has_whatsapp",
        "has_first_patient", "has_first_consultation", "onboarding_dismissed",
        "is_active",
    ]
    for col in cols:
        if column_exists("clinics", col):
            op.drop_column("clinics", col)