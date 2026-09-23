import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import Base, DATABASE_URL  # noqa: E402

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def migration_url():
    return DATABASE_URL

def guard():
    target = os.environ.get("DATABASE_TARGET", "local").lower()
    if target == "production" and os.environ.get("ALLOW_PRODUCTION_MIGRATIONS") != "true":
        raise RuntimeError("Refusing production migration: set ALLOW_PRODUCTION_MIGRATIONS=true explicitly")

def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

def run_offline():
    guard()
    context.configure(url=migration_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_online():
    guard()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = migration_url()
    engine = create_engine(migration_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()

if context.is_offline_mode():
    run_offline()
else:
    run_online()
