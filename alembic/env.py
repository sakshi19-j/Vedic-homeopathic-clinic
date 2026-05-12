import os

from dotenv import load_dotenv
from logging.config import fileConfig

from sqlalchemy import (
    create_engine,
    pool
)

from alembic import context


# =====================================================
# LOAD ENV VARIABLES
# =====================================================

load_dotenv()


# =====================================================
# ALEMBIC CONFIG
# =====================================================

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

print("ALEMBIC DATABASE URL:", db_url)


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
# EXCLUDED SUPABASE SCHEMAS
# =====================================================

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


# =====================================================
# EXCLUDED TABLES
# =====================================================

EXCLUDED_TABLES = {
    "apscheduler_jobs",
    "spatial_ref_sys",
}


# =====================================================
# INCLUDE FILTER
# =====================================================

def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to
):
    """
    Only migrate objects in public schema
    owned by this application.
    """

    # -------------------------------------------------
    # EXCLUDE SUPABASE SCHEMAS
    # -------------------------------------------------

    if (
        hasattr(object, "schema")
        and object.schema in SUPABASE_SCHEMAS
    ):
        return False

    # -------------------------------------------------
    # EXCLUDE TABLES
    # -------------------------------------------------

    if type_ == "table":

        if name in EXCLUDED_TABLES:
            return False

        schema = getattr(
            object,
            "schema",
            None
        )

        if schema and schema != "public":
            return False

    # -------------------------------------------------
    # EXCLUDE INDEXES
    # -------------------------------------------------

    if type_ == "index":

        table = getattr(
            object,
            "table",
            None
        )

        if table is not None:

            table_schema = getattr(
                table,
                "schema",
                None
            )

            if table_schema in SUPABASE_SCHEMAS:
                return False

            if table.name in EXCLUDED_TABLES:
                return False

    return True


# =====================================================
# INCLUDE SCHEMAS
# =====================================================

def include_schemas(name):
    """
    Only include public schema.
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

        include_schemas=False,

        compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


# =====================================================
# ONLINE MIGRATIONS
# =====================================================

def run_migrations_online() -> None:

    connectable = create_engine(

        db_url,

        poolclass=pool.NullPool,

        connect_args={
            "sslmode": "require"
        }
    )

    with connectable.connect() as connection:

        context.configure(

            connection=connection,

            target_metadata=target_metadata,

            include_object=include_object,

            include_schemas=False,

            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


# =====================================================
# RUN ALEMBIC
# =====================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()