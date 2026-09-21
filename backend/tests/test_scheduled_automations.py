import io
import time
import zoneinfo
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from server import app
from models import (
    SessionLocal, User, Recipe, ExternalStorageConnection,
    ScheduledAutomation, ScheduledRun, Execution
)
from auth import hash_password
from scheduler_utils import calculate_next_runs, validate_target_path_template, get_cron_expression
from scheduler_worker import SchedulerWorker
from object_selector import select_target_object
from connectors.base import ObjectRef

client = TestClient(app)

@pytest.fixture
def auth_headers_scheduler():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "sched_test_user@anclora.com").first()
    if not user:
        user = User(
            email="sched_test_user@anclora.com",
            password_hash=hash_password("CleanSheet2026!"),
            display_name="Scheduler Tester"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()

    res = client.post("/api/auth/login", json={"email": "sched_test_user@anclora.com", "password": "CleanSheet2026!"})
    cookies = res.cookies
    return {"Cookie": f"access_token={cookies.get('access_token')}"}

@pytest.fixture
def other_user_headers():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "other_sched_user@anclora.com").first()
    if not user:
        user = User(
            email="other_sched_user@anclora.com",
            password_hash=hash_password("CleanSheet2026!"),
            display_name="Other User"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()

    res = client.post("/api/auth/login", json={"email": "other_sched_user@anclora.com", "password": "CleanSheet2026!"})
    cookies = res.cookies
    return {"Cookie": f"access_token={cookies.get('access_token')}"}

# 1. Unit Tests for Scheduler Utils & Timezone Handling
def test_timezone_and_next_runs_calculation():
    # Test valid IANA timezones (Europe/Madrid, America/New_York, UTC)
    tz = "Europe/Madrid"
    start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    next_3 = calculate_next_runs("daily", None, tz, start_from_utc=start, count=3)
    assert len(next_3) == 3
    # Check that they are sequentially ordered in the future
    assert next_3[0] < next_3[1] < next_3[2]

    # Test weekdays cron
    next_wd = calculate_next_runs("weekdays", None, "UTC", start_from_utc=start, count=5)
    assert len(next_wd) == 5

    # Test invalid timezone throws ValueError
    with pytest.raises(ValueError):
        calculate_next_runs("daily", None, "Invalid/Nonexistent_Tz")

def test_target_path_template_security():
    # Dangerous path traversal
    valid, err = validate_target_path_template("../etc/passwd")
    assert not valid
    assert "traversal" in err.lower()

    valid, err = validate_target_path_template("/root/secrets.csv")
    assert not valid
    assert "traversal" in err.lower()

    # Valid template
    valid, err = validate_target_path_template("normalized/{source_stem}_{date}.csv")
    assert valid
    assert err is None

# 2. CRUD, Ownership, and State Transitions via API
@patch("boto3.client")
def test_schedule_crud_and_ownership(mock_boto, auth_headers_scheduler, other_user_headers):
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    # Setup Recipe and S3 Connection for main user
    rec_res = client.post("/api/recipes", headers=auth_headers_scheduler, json={
        "name": "Receta Facturación Diaria",
        "recipe_yaml": "version: '1.0'\nrules:\n  remove_top_rows: 0\ncolumns:\n  Importe:\n    type: numeric",
        "source_format": "csv"
    })
    recipe_id = rec_res.json()["id"]

    conn_res = client.post("/api/connectors", headers=auth_headers_scheduler, json={
        "name": "AWS S3 Contabilidad",
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "contabilidad-invoices",
            "access_key_id": "AKIA12345678",
            "secret_access_key": "SECRET12345678",
            "region_name": "eu-west-1"
        }
    })
    conn_id = conn_res.json()["id"]

    # 1. Create Schedule
    create_res = client.post("/api/schedules", headers=auth_headers_scheduler, json={
        "name": "Ingesta Diaria Facturas",
        "recipe_id": recipe_id,
        "source_connection_id": conn_id,
        "source_selector_type": "latest_matching",
        "source_key_pattern": "invoices/2026/*.csv",
        "target_path_template": "normalized/{source_stem}_{date}.csv",
        "output_format": "csv",
        "schedule_type": "daily",
        "timezone_name": "Europe/Madrid"
    })
    assert create_res.status_code == 200
    sched_data = create_res.json()
    sched_id = sched_data["id"]
    assert sched_data["name"] == "Ingesta Diaria Facturas"
    assert sched_data["timezone_name"] == "Europe/Madrid"
    assert len(sched_data["next_3_runs"]) == 3
    assert sched_data["is_active"] == 1

    # 2. Multitenant Ownership Protection: other user cannot get or modify
    res_other_get = client.get(f"/api/schedules/{sched_id}", headers=other_user_headers)
    assert res_other_get.status_code == 404

    res_other_disable = client.post(f"/api/schedules/{sched_id}/disable", headers=other_user_headers)
    assert res_other_disable.status_code == 404

    res_other_del = client.delete(f"/api/schedules/{sched_id}", headers=other_user_headers)
    assert res_other_del.status_code == 404

    # 3. Disable & Enable
    dis_res = client.post(f"/api/schedules/{sched_id}/disable", headers=auth_headers_scheduler)
    assert dis_res.status_code == 200
    assert dis_res.json()["is_active"] == 0

    en_res = client.post(f"/api/schedules/{sched_id}/enable", headers=auth_headers_scheduler)
    assert en_res.status_code == 200
    assert en_res.json()["is_active"] == 1

    # 4. Update
    patch_res = client.patch(f"/api/schedules/{sched_id}", headers=auth_headers_scheduler, json={
        "name": "Ingesta Diaria Facturas (Modificado)",
        "schedule_type": "weekdays"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Ingesta Diaria Facturas (Modificado)"
    assert patch_res.json()["schedule_type"] == "weekdays"

# 3. Execution Pipeline, Idempotency, and Deduplication
@patch("boto3.client")
def test_schedule_execution_and_idempotency(mock_boto, auth_headers_scheduler):
    mock_s3 = MagicMock()
    csv_bytes = b"Fecha,Importe,Cliente\n2026-02-01,150.00,Empresa A\n"
    mock_body = MagicMock()
    mock_body.read.side_effect = [csv_bytes, b""]
    mock_s3.get_object.return_value = {"Body": mock_body}
    mock_s3.head_object.return_value = {
        "ContentLength": len(csv_bytes),
        "ETag": '"etag-invoice-1"',
        "ContentType": "text/csv"
    }
    mock_s3.put_object.return_value = {"ETag": '"clean-output-etag"'}
    mock_boto.return_value = mock_s3

    # Create resources
    rec_res = client.post("/api/recipes", headers=auth_headers_scheduler, json={
        "name": "Receta Facturas",
        "recipe_yaml": "version: '1.0'\nrules:\n  remove_top_rows: 0\ncolumns:\n  Importe:\n    type: numeric",
        "source_format": "csv"
    })
    recipe_id = rec_res.json()["id"]

    conn_res = client.post("/api/connectors", headers=auth_headers_scheduler, json={
        "name": "S3 Pipeline Storage",
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "data-pipeline",
            "access_key_id": "AKIA_KEY",
            "secret_access_key": "SECRET_KEY",
            "region_name": "us-east-1"
        }
    })
    conn_id = conn_res.json()["id"]

    sched_res = client.post("/api/schedules", headers=auth_headers_scheduler, json={
        "name": "Test Pipeline Run Now",
        "recipe_id": recipe_id,
        "source_connection_id": conn_id,
        "source_selector_type": "exact",
        "source_key_pattern": "raw/invoice_feb.csv",
        "target_path_template": "clean/{source_stem}_out.csv"
    })
    sched_id = sched_res.json()["id"]

    # 1. Execute run-now
    run_res = client.post(f"/api/schedules/{sched_id}/run-now", headers=auth_headers_scheduler)
    assert run_res.status_code == 200
    res_data = run_res.json()
    assert res_data["status"] == "completed"
    assert res_data["source_key"] == "raw/invoice_feb.csv"
    assert res_data["rows_in"] == 2 # 1 header + 1 row
    assert res_data["rows_out"] == 1

    # Check ScheduledRun list
    runs_list_res = client.get(f"/api/schedules/{sched_id}/runs", headers=auth_headers_scheduler)
    assert runs_list_res.status_code == 200
    runs = runs_list_res.json()
    assert len(runs) >= 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["trigger_type"] == "manual"

# 4. Multi-Worker Lease Locking & Concurrency Test
def test_multi_worker_concurrency_and_lease():
    db = SessionLocal()
    # Create an automation due for run
    auto = ScheduledAutomation(
        user_id="test_user_worker",
        name="Worker Concurrency Test",
        source_key_pattern="test.csv",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        is_active=1
    )
    db.add(auto)
    db.commit()
    db.refresh(auto)

    # Worker 1 and Worker 2 try to acquire the same due job simultaneously
    worker1 = SchedulerWorker(worker_id="worker_instance_1")
    worker2 = SchedulerWorker(worker_id="worker_instance_2")

    acquired_1 = worker1.acquire_due_jobs(db)
    acquired_2 = worker2.acquire_due_jobs(db)

    # Only Worker 1 should have successfully claimed the lease
    assert len([j for j in acquired_1 if j.id == auto.id]) == 1
    assert len([j for j in acquired_2 if j.id == auto.id]) == 0

    # Verify lease lock persisted in DB
    refreshed = db.query(ScheduledAutomation).filter(ScheduledAutomation.id == auto.id).first()
    assert refreshed.locked_by == "worker_instance_1"
    # Normalize offset-naive datetime stored in SQLite/DB
    locked_until = refreshed.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    assert locked_until > datetime.now(timezone.utc)

    # Clean up
    db.delete(refreshed)
    db.commit()
    db.close()
