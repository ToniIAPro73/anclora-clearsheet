import io
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from server import app
from models import SessionLocal, User, SourceFile, Recipe, Execution, AuthWhitelist
from auth import hash_password, create_access_token

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    return TestClient(app)

def create_active_user(db, email, password="TestPassword123!"):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=hash_password(password),
            display_name=email.split("@")[0],
            status="active"
        )
        db.add(user)
        db.flush()

    wl = db.query(AuthWhitelist).filter(AuthWhitelist.email == email).first()
    if not wl:
        wl = AuthWhitelist(
            id=str(uuid.uuid4()),
            email=email,
            status="active",
            user_id=user.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl)
    else:
        wl.user_id = user.id
        wl.status = "active"
    db.commit()
    db.refresh(user)
    return user

def auth_headers(user):
    token = create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}

# ---------- 1. Anonymous Access Rejection (401) ----------

def test_anonymous_upload_denied(client):
    csv_content = b"col1,col2\nval1,val2"
    r = client.post(
        "/api/files/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert r.status_code == 401

def test_anonymous_analyze_denied(client):
    r = client.get("/api/files/fake-file-id/analyze")
    assert r.status_code == 401

def test_anonymous_preview_denied(client):
    r = client.post("/api/files/preview", json={"file_id": "fake-file-id", "rules": {}})
    assert r.status_code == 401

def test_anonymous_export_denied(client):
    r = client.post("/api/files/export", json={"file_id": "fake-file-id", "rules": {}})
    assert r.status_code == 401

def test_anonymous_batch_process_denied(client):
    csv_content = b"a,b\n1,2"
    r = client.post(
        "/api/batch/process",
        files=[("files", ("test.csv", io.BytesIO(csv_content), "text/csv"))]
    )
    assert r.status_code == 401

def test_anonymous_batch_download_denied(client):
    r = client.get("/api/batch/download/some_fake_key.zip")
    assert r.status_code == 401

def test_anonymous_detect_dialect_denied(client):
    csv_content = b"a;b;c\n1;2;3"
    r = client.post(
        "/api/files/detect-dialect",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    )
    assert r.status_code == 401

def test_anonymous_samples_denied(client):
    r = client.get("/api/samples/erp")
    assert r.status_code == 401

def test_anonymous_storage_direct_upload_denied(client):
    r = client.post("/api/storage/direct-upload-url", json={"filename": "test.xlsx"})
    assert r.status_code == 401

def test_anonymous_connector_test_denied(client):
    r = client.post("/api/connectors/test", json={
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "test",
            "access_key_id": "key",
            "secret_access_key": "sec"
        }
    })
    assert r.status_code == 401

# ---------- 2. Cross-User Isolation & IDOR Protection ----------

def test_user_a_cannot_access_user_b_file(client, db_session):
    user_a = create_active_user(db_session, "user_a@anclora.local")
    user_b = create_active_user(db_session, "user_b@anclora.local")

    # User B uploads a file
    csv_b = b"header1,header2\n10,20\n30,40"
    upload_b = client.post(
        "/api/files/upload",
        headers=auth_headers(user_b),
        files={"file": ("b_data.csv", io.BytesIO(csv_b), "text/csv")}
    )
    assert upload_b.status_code == 200
    file_b_id = upload_b.json()["file_id"]

    # User A attempts to analyze User B's file -> 404 (Not found or not authorized)
    r_analyze = client.get(f"/api/files/{file_b_id}/analyze", headers=auth_headers(user_a))
    assert r_analyze.status_code == 404

    # User A attempts to preview User B's file -> 404
    r_preview = client.post(
        "/api/files/preview",
        headers=auth_headers(user_a),
        json={"file_id": file_b_id, "rules": {}}
    )
    assert r_preview.status_code == 404

    # User A attempts to export User B's file -> 404
    r_export = client.post(
        "/api/files/export",
        headers=auth_headers(user_a),
        json={"file_id": file_b_id, "rules": {}}
    )
    assert r_export.status_code == 404

def test_user_a_cannot_use_user_b_recipe(client, db_session):
    user_a = create_active_user(db_session, "user_a2@anclora.local")
    user_b = create_active_user(db_session, "user_b2@anclora.local")

    # User B creates a private recipe
    recipe_b = Recipe(
        id=str(uuid.uuid4()),
        user_id=user_b.id,
        name="Private B Recipe",
        recipe_version="1.0",
        definition_yaml="recipe_version: '1.0'\nrules: {}\ncolumns: {}\n"
    )
    db_session.add(recipe_b)
    db_session.commit()

    # User A creates a file
    csv_a = b"col1,col2\nval1,val2"
    upload_a = client.post(
        "/api/files/upload",
        headers=auth_headers(user_a),
        files={"file": ("a_data.csv", io.BytesIO(csv_a), "text/csv")}
    )
    assert upload_a.status_code == 200
    file_a_id = upload_a.json()["file_id"]

    # User A attempts to validate compatibility with User B's recipe -> 404
    r_comp = client.post(
        "/api/recipes/validate-compatibility",
        headers=auth_headers(user_a),
        json={"recipe_id": recipe_b.id, "file_id": file_a_id}
    )
    assert r_comp.status_code == 404

    # User A attempts batch process using User B's recipe -> 404
    r_batch = client.post(
        "/api/batch/process",
        headers=auth_headers(user_a),
        data={"recipe_id": recipe_b.id},
        files=[("files", ("test.csv", io.BytesIO(csv_a), "text/csv"))]
    )
    assert r_batch.status_code in (403, 404)

def test_user_a_cannot_download_user_b_batch(client, db_session):
    user_a = create_active_user(db_session, "user_a3@anclora.local")
    user_b = create_active_user(db_session, "user_b3@anclora.local")

    # Create dummy execution for User B
    fake_zip_key = f"fake_batch_{uuid.uuid4().hex}.zip"
    b_exec = Execution(
        id=str(uuid.uuid4()),
        user_id=user_b.id,
        file_name="[BATCH_2_FILES] Test",
        rows_input=10,
        rows_output=10,
        columns_input=2,
        columns_output=2,
        transformations_count=1,
        duration_ms=100,
        result_storage_path=fake_zip_key,
        status="completed"
    )
    db_session.add(b_exec)
    db_session.commit()

    # User A attempts to download User B's batch zip -> 404
    r_down = client.get(f"/api/batch/download/{fake_zip_key}", headers=auth_headers(user_a))
    assert r_down.status_code == 404
