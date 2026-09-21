import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from scheduler_dispatcher import SchedulerJobDispatcher
from models import SessionLocal, User, Recipe, ExternalStorageConnection, ScheduledAutomation, ScheduledRun
from auth import hash_password

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

@patch("boto3.client")
def test_transient_vs_permanent_errors(mock_boto, db_session):
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    # Setup resources (idempotent lookup)
    user = db_session.query(User).filter(User.email == "retry_test@example.com").first()
    if not user:
        user = User(
            email="retry_test@example.com",
            password_hash=hash_password("Pass123!"),
            display_name="Retry Test"
        )
        db_session.add(user)
        db_session.commit()

    conn = ExternalStorageConnection(
        user_id=user.id,
        name="Conn",
        provider_type="s3_compatible",
        encrypted_config="",
    )
    db_session.add(conn)
    db_session.commit()

    # Recipe with required column 'Importe'
    recipe = Recipe(
        user_id=user.id,
        name="Recipe Drift",
        definition_yaml="""
version: '1.0'
rules:
  remove_top_rows: 0
columns:
  Importe:
    type: numeric
""",
        source_format="csv"
    )
    db_session.add(recipe)
    db_session.commit()

    auto = ScheduledAutomation(
        user_id=user.id,
        name="Auto Drift Test",
        recipe_id=recipe.id,
        source_connection_id=conn.id,
        source_selector_type="exact",
        source_key_pattern="test_drift.csv"
    )
    db_session.add(auto)
    db_session.commit()

    # Case 1: Remote file has MISSING required column -> BLOCKING DRIFT
    # File only has 'Fecha', missing 'Importe'
    csv_bytes = b"Fecha,Cliente\n2026-01-01,Empresa X\n"
    mock_body = MagicMock()
    mock_body.read.side_effect = [csv_bytes, b""]
    mock_s3.get_object.return_value = {"Body": mock_body}
    mock_s3.head_object.return_value = {"ContentLength": len(csv_bytes), "ETag": '"etag1"'}

    result = SchedulerJobDispatcher.execute_job(
        db=db_session,
        automation=auto,
        scheduled_for=datetime.now(timezone.utc),
        trigger_type="scheduled"
    )

    # Must FAIL deterministically, never re-attempted
    assert result["status"] == "failed"
    assert "bloqueante" in result["error"].lower()

    # Verify ScheduledRun status is 'failed' and has error
    run_record = db_session.query(ScheduledRun).filter(ScheduledRun.id == result["run_id"]).first()
    assert run_record.status == "failed"
    assert "bloqueante" in run_record.error_message.lower()

    # Clean up
    db_session.delete(auto)
    db_session.delete(recipe)
    db_session.delete(conn)
    db_session.commit()
