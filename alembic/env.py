import os
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull DB URL directly — bypass configparser which chokes on % in password
db_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")

# Import ALL models so Alembic can detect changes
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


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()