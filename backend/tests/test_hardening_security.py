import pytest
import io
import os
import time
import hmac
import hashlib
import zipfile
import json
import yaml
import pandas as pd
from fastapi.testclient import TestClient

from server import app
from models import init_db, SessionLocal, User, Recipe, AutomationWebhook
from auth import hash_password
from recipe_service import verify_hmac_signature, validate_file_content

init_db()
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_users_and_recipes():
    db = SessionLocal()
    # User A (owner)
    user_a = db.query(User).filter(User.email == "user_a@test.com").first()
    if not user_a:
        user_a = User(email="user_a@test.com", password_hash=hash_password("Pass123!"), display_name="User A")
        db.add(user_a)
        db.commit()
        db.refresh(user_a)

    # User B (adversary)
    user_b = db.query(User).filter(User.email == "user_b@test.com").first()
    if not user_b:
        user_b = User(email="user_b@test.com", password_hash=hash_password("Pass123!"), display_name="User B")
        db.add(user_b)
        db.commit()
        db.refresh(user_b)

    # Recipe for User A
    recipe_yaml = """
recipe_version: "1.0"
name: "Recipe A Test"
structure_fingerprint: "fp_test_a"
source:
  sheet: "Sheet1"
rules:
  remove_top_rows: 1
  remove_empty_rows: true
  remove_empty_columns: true
  decimal_separator: ","
  output_decimal_separator: "."
columns:
  Fecha:
    type: date
  Importe:
    type: decimal
"""
    recipe_a = db.query(Recipe).filter(Recipe.user_id == user_a.id, Recipe.name == "Recipe A Test").first()
    if not recipe_a:
        recipe_a = Recipe(
            user_id=user_a.id,
            name="Recipe A Test",
            recipe_version="1.0",
            definition_yaml=recipe_yaml,
            structure_fingerprint="fp_test_a"
        )
        db.add(recipe_a)
        db.commit()
        db.refresh(recipe_a)

    # Webhook for User A
    webhook_a = db.query(AutomationWebhook).filter(AutomationWebhook.user_id == user_a.id).first()
    if not webhook_a:
        webhook_a = AutomationWebhook(
            user_id=user_a.id,
            recipe_id=recipe_a.id,
            name="Webhook Test A",
            token="wh_test_token_hardening_123",
            secret_key="secret_key_test_hardening_456",
            target_format="xlsx"
        )
        db.add(webhook_a)
        db.commit()
        db.refresh(webhook_a)

    res = {
        "user_a_id": str(user_a.id),
        "user_b_id": str(user_b.id),
        "recipe_a_id": str(recipe_a.id),
        "webhook_token": str(webhook_a.token),
        "webhook_secret": str(webhook_a.secret_key)
    }
    db.close()
    return res

# ----------------- 1. HMAC Signature & Replay Attacks -----------------
def test_hmac_valid_and_invalid_signature():
    secret = "my_super_secret"
    payload = b"Hello, World spreadsheet data"
    ts = str(int(time.time()))
    payload_hash = hashlib.sha256(payload).hexdigest()
    valid_sig = hmac.new(secret.encode("utf-8"), f"{ts}.{payload_hash}".encode("utf-8"), hashlib.sha256).hexdigest()

    # Valid check
    is_valid, msg = verify_hmac_signature(secret, payload, f"t={ts},v1={valid_sig}", ts)
    assert is_valid is True

    # Invalid signature (wrong secret)
    is_valid_bad, msg_bad = verify_hmac_signature("wrong_secret", payload, f"t={ts},v1={valid_sig}", ts)
    assert is_valid_bad is False
    assert "Firma HMAC inválida" in msg_bad

def test_hmac_replay_attack_protection():
    secret = "my_super_secret"
    payload = b"Sample data"
    # Timestamp from 10 minutes ago (> 300s drift)
    old_ts = str(int(time.time()) - 600)
    payload_hash = hashlib.sha256(payload).hexdigest()
    sig = hmac.new(secret.encode("utf-8"), f"{old_ts}.{payload_hash}".encode("utf-8"), hashlib.sha256).hexdigest()

    is_valid, msg = verify_hmac_signature(secret, payload, f"t={old_ts},v1={sig}", old_ts, max_drift_seconds=300)
    assert is_valid is False
    assert "Replay attack" in msg

# ----------------- 2. Webhook Drop Security -----------------
def test_webhook_drop_with_hmac(setup_users_and_recipes):
    token = setup_users_and_recipes["webhook_token"]
    secret = setup_users_and_recipes["webhook_secret"]

    csv_content = b"Banner\nFecha,Importe\n01/05/2026,\"1.250,50\"\n"
    ts = str(int(time.time()))
    payload_hash = hashlib.sha256(csv_content).hexdigest()
    sig = hmac.new(secret.encode("utf-8"), f"{ts}.{payload_hash}".encode("utf-8"), hashlib.sha256).hexdigest()

    # 1. Valid request with signature
    res = client.post(
        f"/api/webhooks/drop/{token}",
        files={"file": ("ventas.csv", csv_content, "text/csv")},
        headers={
            "X-CleanSheet-Timestamp": ts,
            "X-CleanSheet-Signature": f"t={ts},v1={sig}"
        }
    )
    assert res.status_code == 200

    # 2. Tampered payload with old signature -> 401
    tampered_content = b"Banner\nFecha,Importe\n01/05/2026,\"9.999,99\"\n"
    res_tampered = client.post(
        f"/api/webhooks/drop/{token}",
        files={"file": ("ventas.csv", tampered_content, "text/csv")},
        headers={
            "X-CleanSheet-Timestamp": ts,
            "X-CleanSheet-Signature": f"t={ts},v1={sig}"
        }
    )
    assert res_tampered.status_code == 401

# ----------------- 3. Recipe Ownership & Authorization -----------------
def test_recipe_ownership_authorization(setup_users_and_recipes):
    recipe_a_id = setup_users_and_recipes["recipe_a_id"]

    # Login as User B using client instance to preserve session cookies
    client_b = TestClient(app)
    login_b = client_b.post("/api/auth/login", json={"email": "user_b@test.com", "password": "Pass123!"})
    assert login_b.status_code == 200

    # User B tries to batch process using User A's private recipe -> 403 Forbidden
    csv_file = ("test.csv", b"Fecha,Importe\n01/05/2026,100\n", "text/csv")
    res = client_b.post(
        "/api/batch/process",
        files=[("files", csv_file)],
        data={"recipe_id": recipe_a_id, "output_format": "xlsx"}
    )
    assert res.status_code == 403
    assert "No tienes autorización" in res.json()["detail"]

# ----------------- 4. Batch Partial Results & Manifest -----------------
def test_batch_partial_results_and_manifest():
    client.post("/api/auth/login", json={"email": "user_a@test.com", "password": "Pass123!"})
    # Submit 3 files: 1 valid CSV, 1 corrupted XLSX (wrong magic bytes), 1 invalid extension (.exe)
    valid_csv = ("valid.csv", b"Titulo\nFecha,Importe\n01/05/2026,\"1.200,50\"\n", "text/csv")
    corrupt_xlsx = ("corrupt.xlsx", b"NOT_A_REAL_ZIP_HEADER_JUST_RANDOM_TEXT", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    invalid_ext = ("malicious.exe", b"binary_data", "application/octet-stream")

    res = client.post(
        "/api/batch/process",
        files=[("files", valid_csv), ("files", corrupt_xlsx), ("files", invalid_ext)],
        data={"output_format": "xlsx"}
    )
    assert res.status_code == 200
    data = res.json()

    assert data["total_files"] == 3
    assert data["successful_files"] == 1
    assert data["failed_files"] == 2

    # Download zip and inspect contents
    zip_key = data["zip_storage_key"]
    res_zip = client.get(f"/api/batch/download/{zip_key}")
    assert res_zip.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(res_zip.content))
    filenames = zf.namelist()
    assert "manifest.json" in filenames
    assert "manifest.csv" in filenames
    assert any("valid.xlsx" in f for f in filenames)
    assert not any("corrupt" in f for f in filenames)
    assert not any("malicious" in f for f in filenames)

    # Validate manifest.json content
    manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest_data["successful_count"] == 1
    assert manifest_data["failed_count"] == 2
    assert any(r["original_name"] == "corrupt.xlsx" and r["status"] == "failed" for r in manifest_data["records"])
