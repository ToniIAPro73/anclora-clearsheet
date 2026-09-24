"""Add closed access whitelist, users.status, and auth audit events.

Revision ID: 0002_closed_access_whitelist
Revises: 0001_initial_schema
Create Date: 2026-09-24
"""
import uuid
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_closed_access_whitelist"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Add status column to users table if not already present
    inspector = sa.inspect(bind)
    user_columns = [c["name"] for c in inspector.get_columns("users")]
    if "status" not in user_columns:
        op.add_column(
            "users",
            sa.Column("status", sa.String(20), nullable=False, server_default="active")
        )

    # 2. Create auth_whitelist table if not exists
    existing_tables = set(inspector.get_table_names(schema="public" if is_postgres else None))
    if "auth_whitelist" not in existing_tables:
        op.create_table(
            "auth_whitelist",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True),
            sa.Column("created_by", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_auth_whitelist_email", "auth_whitelist", ["email"])
        op.create_index("ix_auth_whitelist_status", "auth_whitelist", ["status"])
        op.create_index("ix_auth_whitelist_expires_at", "auth_whitelist", ["expires_at"])
        op.create_index("ix_auth_whitelist_user_id", "auth_whitelist", ["user_id"])

    # 3. Create auth_audit_events table if not exists
    if "auth_audit_events" not in existing_tables:
        json_type = postgresql.JSONB if is_postgres else sa.JSON
        op.create_table(
            "auth_audit_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event", sa.String(50), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("metadata_json", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_auth_audit_events_event", "auth_audit_events", ["event"])
        op.create_index("ix_auth_audit_events_email", "auth_audit_events", ["email"])
        op.create_index("ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"])
        op.create_index("ix_auth_audit_events_created_at", "auth_audit_events", ["created_at"])

    # 4. Backfill existing users into auth_whitelist
    users_table = sa.table(
        "users",
        sa.column("id", sa.String(36)),
        sa.column("email", sa.String(255)),
        sa.column("status", sa.String(20)),
    )
    whitelist_table = sa.table(
        "auth_whitelist",
        sa.column("id", sa.String(36)),
        sa.column("email", sa.String(255)),
        sa.column("status", sa.String(20)),
        sa.column("token_hash", sa.String(64)),
        sa.column("expires_at", sa.DateTime(timezone=True)),
        sa.column("activated_at", sa.DateTime(timezone=True)),
        sa.column("user_id", sa.String(36)),
        sa.column("created_by", sa.String(255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)
    bind.execute(sa.update(users_table).where(users_table.c.status.is_(None)).values(status="active"))
    users = bind.execute(sa.select(users_table.c.id, users_table.c.email)).fetchall()
    for user_id, raw_email in users:
        norm_email = raw_email.strip().lower()
        # Check if already present in auth_whitelist
        existing = bind.execute(
            sa.select(whitelist_table.c.id).where(whitelist_table.c.email == norm_email)
        ).scalar()
        if not existing:
            bind.execute(
                whitelist_table.insert().values(
                    id=str(uuid.uuid4()),
                    email=norm_email,
                    status="active",
                    token_hash=None,
                    expires_at=None,
                    activated_at=now,
                    user_id=user_id,
                    created_by="migration_existing_user",
                    created_at=now,
                    updated_at=now,
                )
            )

def downgrade() -> None:
    raise RuntimeError("CleanSheet production schema is forward-only; destructive downgrade is forbidden")
