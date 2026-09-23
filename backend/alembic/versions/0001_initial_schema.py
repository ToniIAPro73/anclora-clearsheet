"""Adopt and own the CleanSheet PostgreSQL schema.

The target Neon database was provisioned empty and was initialized once by the
pre-Alembic bootstrap. This migration is deliberately forward-only: it verifies
that no foreign application tables exist, creates only missing model tables, and
then records the real Alembic revision. Runtime startup never calls create_all.
"""
from alembic import op
from sqlalchemy import inspect

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    from models import Base
    bind = op.get_bind()
    inspector = inspect(bind)
    expected = set(Base.metadata.tables)
    existing = set(inspector.get_table_names(schema="public"))
    unexpected = existing - expected - {"alembic_version"}
    if unexpected:
        raise RuntimeError(f"Unexpected public tables; refusing adoption: {sorted(unexpected)}")
    # SQLAlchemy emits the complete declarative schema only for missing objects.
    # It does not drop, truncate, or rewrite existing rows.
    Base.metadata.create_all(bind=bind, checkfirst=True)

def downgrade():
    raise RuntimeError("CleanSheet production schema is forward-only; destructive downgrade is forbidden")
