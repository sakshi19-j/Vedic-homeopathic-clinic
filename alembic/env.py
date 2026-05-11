import os
from logging.config import fileConfig

from sqlalchemy import (
    create_engine,
    pool
)

from alembic import context


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# =====================================================
# DATABASE URL
# =====================================================

db_url = os.getenv(
    "DATABASE_URL",
    ""
).replace(
    "postgres://",
    "postgresql://"
)


# =====================================================
# IMPORT ALL MODELS
# =====================================================

from app.models.base import Base

from app.models import (
    clinic,
    user,
    patient,
    visit,
    billing,
    reminder,
    queue,
    staff,
    appointment,
    import_job,
    audit_log,
)


target_metadata = Base.metadata


# =====================================================
# EXCLUDE FILTER
# =====================================================
# Supabase manages auth/storage/realtime/vault schemas
# internally. Alembic must never touch them.
# =====================================================

# Schemas owned by Supabase — never migrate these
SUPABASE_SCHEMAS = {
    "auth",
    "storage",
    "realtime",
    "vault",
    "extensions",
    "graphql",
    "graphql_public",
    "pgbouncer",
    "pgsodium",
    "pgsodium_masks",
    "supabase_functions",
    "supabase_migrations",
    "_realtime",
    "information_schema",
    "pg_catalog",
    "pg_toast",
}

# Tables outside Supabase schemas that Alembic
# should still ignore
EXCLUDED_TABLES = {
    "apscheduler_jobs",
    "spatial_ref_sys",
}


def include_object(object, name, type_, reflected, compare_to):
    """
    Only migrate objects in the public schema
    that belong to this application.
    """

    # ── Exclude entire Supabase-owned schemas ─────
    if hasattr(object, "schema") and object.schema in SUPABASE_SCHEMAS:
        return False

    # ── Exclude by table name ─────────────────────
    if type_ == "table":
        if name in EXCLUDED_TABLES:
            return False

        # Exclude any reflected table that has
        # a schema prefix we don't own
        schema = getattr(object, "schema", None)
        if schema and schema != "public":
            return False

    # ── Exclude indexes on excluded tables ────────
    if type_ == "index":
        table = getattr(object, "table", None)
        if table is not None:
            table_schema = getattr(table, "schema", None)
            if table_schema in SUPABASE_SCHEMAS:
                return False
            if table.name in EXCLUDED_TABLES:
                return False

    return True


def include_schemas(name):
    """
    Only include the public schema.
    Keeps Alembic from even looking at
    auth/storage/realtime.
    """
    return name in ("public", None)


# =====================================================
# OFFLINE MIGRATIONS
# =====================================================

def run_migrations_offline() -> None:

    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        include_object=include_object,
        include_schemas=False,         # ✅ offline — public only
    )

    with context.begin_transaction():
        context.run_migrations()


# =====================================================
# ONLINE MIGRATIONS
# =====================================================

def run_migrations_online() -> None:

    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,     # ✅ KEY FIX — False stops Supabase schema scanning
        )

        with context.begin_transaction():
            context.run_migrations()


# =====================================================
# RUN
# =====================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()