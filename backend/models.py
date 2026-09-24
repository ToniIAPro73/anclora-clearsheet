import os
import uuid
import secrets
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime as SQLDateTime, Text, ForeignKey, JSON, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import StaticPool

# Every persisted instant is timezone-aware. `timezone_name` remains an explicit
# IANA identifier on scheduled automations and is not inferred from the server.
DateTime = SQLDateTime(timezone=True)

# Database URL configuration
# Default supports PostgreSQL / Neon (e.g. postgresql://user:password@neon.tech/dbname)
# Falls back to local SQLite with thread safety for dev if PostgreSQL is not active
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_TARGET = os.environ.get("DATABASE_TARGET", "local").lower()
if not DATABASE_URL:
    # Use SQLite for reliable zero-setup development, fully compatible schema with PostgreSQL
    DATABASE_URL = "sqlite:////tmp/cleansheet.db"

is_sqlite = DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active", server_default="active")  # active | disabled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="user")
    whitelist_entry = relationship("AuthWhitelist", back_populates="user", uselist=False)

class AuthWhitelist(Base):
    __tablename__ = "auth_whitelist"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | active | revoked
    token_hash = Column(String(64), unique=True, nullable=True)  # SHA-256 hex
    expires_at = Column(DateTime, nullable=True, index=True)
    activated_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="whitelist_entry")
class AuthAuditEvent(Base):
    __tablename__ = "auth_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class SourceFile(Base):
    __tablename__ = "source_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    structure_fingerprint = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    recipe_version = Column(String(20), default="1.0")
    definition_yaml = Column(Text, nullable=False)
    structure_fingerprint = Column(String(64), nullable=True, index=True)
    source_format = Column(String(20), default="xlsx")
    execution_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="recipes")
    executions = relationship("Execution", back_populates="recipe")

class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source_file_id = Column(String(36), ForeignKey("source_files.id", ondelete="SET NULL"), nullable=True)
    recipe_id = Column(String(36), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="completed")
    file_name = Column(String(255), nullable=True)
    rows_input = Column(Integer, default=0)
    rows_output = Column(Integer, default=0)
    columns_input = Column(Integer, default=0)
    columns_output = Column(Integer, default=0)
    transformations_count = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    result_storage_path = Column(String(512), nullable=True)
    result_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="executions")
    recipe = relationship("Recipe", back_populates="executions")

class AutomationWebhook(Base):
    __tablename__ = "automation_webhooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe_id = Column(String(36), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    secret_key = Column(String(255), nullable=False)
    secret_preview = Column(String(16), nullable=True) # First/last chars e.g. sec_abc...1234
    target_format = Column(String(20), default="xlsx")
    is_active = Column(Integer, default=1)
    runs_count = Column(Integer, default=0)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    recipe = relationship("Recipe")

class ProcessedNonce(Base):
    """Stores used nonces / idempotency keys with TTL for distributed anti-replay attacks."""
    __tablename__ = "processed_nonces"

    nonce = Column(String(128), primary_key=True)
    webhook_token = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class ExternalStorageConnection(Base):
    """
    User-owned External Storage Connections (S3-compatible, Google Drive, OneDrive, etc.).
    All credentials and endpoint configs are encrypted at-rest using AES-256-GCM.
    Never exposes raw secrets or keys to the frontend.
    """
    __tablename__ = "external_storage_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False, default="s3_compatible") # s3_compatible, gdrive, onedrive
    encrypted_config = Column(Text, nullable=False) # AES-256-GCM encrypted JSON with credentials
    config_preview = Column(JSON, nullable=True) # Safe unencrypted non-sensitive metadata: bucket, endpoint_host, region, key_id_preview
    is_active = Column(Integer, default=1)
    last_tested_at = Column(DateTime, nullable=True)
    last_test_status = Column(String(50), nullable=True) # success, failed
    last_test_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")

class ScheduledAutomation(Base):
    """
    User-owned Scheduled Automations connecting Cloud Source -> Deterministic Recipe -> Cloud Target.
    Managed independently from the web layer with distributed lease locking in PostgreSQL.
    """
    __tablename__ = "scheduled_automations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    recipe_id = Column(String(36), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True, index=True)
    source_connection_id = Column(String(36), ForeignKey("external_storage_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    source_selector_type = Column(String(50), nullable=False, default="exact") # exact | prefix | latest_matching
    source_key_pattern = Column(String(512), nullable=False) # exact key or prefix/glob pattern
    target_connection_id = Column(String(36), ForeignKey("external_storage_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    target_path_strategy = Column(String(50), nullable=False, default="templated") # templated | mirror | custom
    target_path_template = Column(String(512), nullable=True) # e.g. normalized/{source_stem}_{date}.csv
    output_format = Column(String(10), nullable=False, default="csv") # csv | xlsx

    # Scheduling details
    schedule_type = Column(String(50), nullable=False, default="daily") # daily | weekdays | weekly | monthly | cron
    cron_expression = Column(String(120), nullable=True)
    timezone_name = Column(String(100), nullable=False, default="UTC") # Explicit IANA timezone, e.g. Europe/Madrid, UTC
    is_active = Column(Integer, default=1, index=True)

    # Runtime state & distributed lease
    locked_until = Column(DateTime, nullable=True, index=True) # Distributed lease lock to prevent multi-worker concurrency
    locked_by = Column(String(100), nullable=True) # Worker hostname/instance ID
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    last_status = Column(String(50), nullable=True) # completed | skipped | failed | needs_attention
    last_error = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, default=0)

    # State cache for deduplication (source identity)
    last_processed_object_key = Column(String(512), nullable=True)
    last_processed_version_id = Column(String(255), nullable=True)
    last_processed_etag = Column(String(255), nullable=True)
    last_processed_timestamp = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    recipe = relationship("Recipe")
    source_connection = relationship("ExternalStorageConnection", foreign_keys=[source_connection_id])
    target_connection = relationship("ExternalStorageConnection", foreign_keys=[target_connection_id])

class ScheduledRun(Base):
    """
    Auditable persistent execution run for Scheduled Automations.
    Enforces idempotency via unique constraint on (automation_id, scheduled_for).
    """
    __tablename__ = "scheduled_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    automation_id = Column(String(36), ForeignKey("scheduled_automations.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False, index=True) # Intended schedule timestamp (or manual trigger timestamp)
    trigger_type = Column(String(20), nullable=False, default="scheduled") # scheduled | manual
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="running") # running | completed | skipped | failed
    attempt_count = Column(Integer, default=1)
    skip_reason = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Audit references & metrics
    execution_id = Column(String(36), ForeignKey("executions.id", ondelete="SET NULL"), nullable=True)
    source_key = Column(String(512), nullable=True)
    source_version_id = Column(String(255), nullable=True)
    source_etag = Column(String(255), nullable=True)
    target_key = Column(String(512), nullable=True)
    rows_in = Column(Integer, default=0)
    rows_out = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    schema_status = Column(String(50), nullable=True)
    drift_items = Column(JSON, nullable=True)
    applied_aliases = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("automation_id", "scheduled_for", name="uq_automation_scheduled_for"),
    )

    automation = relationship("ScheduledAutomation")
    execution = relationship("Execution")

def init_db():
    if is_sqlite:
        # SQLite is intentionally limited to isolated local/CI runs.
        try:
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                unlinked = db.query(User).all()
                now = datetime.now(timezone.utc)
                for u in unlinked:
                    if not u.status:
                        u.status = "active"
                    clean_email = (u.email or "").strip().lower()
                    wl = db.query(AuthWhitelist).filter(
                        (AuthWhitelist.user_id == u.id) | (AuthWhitelist.email == clean_email)
                    ).first()
                    if not wl:
                        wl = AuthWhitelist(
                            id=str(uuid.uuid4()),
                            email=clean_email,
                            status="active",
                            user_id=u.id,
                            created_by="init_db_sync",
                            created_at=now,
                            updated_at=now,
                            activated_at=now
                        )
                        db.add(wl)
                db.commit()
        except Exception:
            # Parallel test workers or pre-existing schema
            pass
        return
    # PostgreSQL production schema is migration-owned. Startup may verify
    # connectivity, but it must never create or alter production tables.
    check_database()

def check_database():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
