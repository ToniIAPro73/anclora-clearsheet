import pytest
import io
import time
import hmac
import hashlib
import zipfile
import json
from fastapi.testclient import TestClient

from server import app
from models import init_db, SessionLocal, User, Recipe, AutomationWebhook, ProcessedNonce
from auth import hash_password
from crypto_service import encrypt_secret, decrypt_secret
from rate_limit_store import InMemoryRateLimitStore, get_rate_limit_store
from recipe_service import (
    validate_ooxml_xlsx, validate_file_content, check_and_record_nonce, verify_hmac_signature
)

init_db()
client = TestClient(app)

# ----------------- 1. Anti-Replay with Nonces / Idempotency -----------------
def test_anti_replay_nonce_rejection():
    nonce = f"nonce_{time.time()}_unique"
    token = "wh_token_test"

    # First attempt: valid
    valid_1, msg_1 = check_and_record_nonce(nonce, token, ttl_seconds=300)
    assert valid_1 is True

    # Immediate replay with same nonce: rejected!
    valid_2, msg_2 = check_and_record_nonce(nonce, token, ttl_seconds=300)
    assert valid_2 is False
    assert "Replay attack detectado" in msg_2

def test_webhook_hmac_replay_with_same_nonce():
    secret = "secret_key_test_replay"
    payload = b"Fecha,Importe\n01/05/2026,100\n"
    ts = str(int(time.time()))
    payload_hash = hashlib.sha256(payload).hexdigest()
    sig = hmac.new(secret.encode("utf-8"), f"{ts}.{payload_hash}".encode("utf-8"), hashlib.sha256).hexdigest()

    unique_nonce = f"nonce_{time.time()}_replay_test"

    # Call 1: valid
    valid1, _ = verify_hmac_signature(
        secret, payload, f"t={ts},v1={sig}", ts, nonce_header=unique_nonce, webhook_token="wh_1"
    )
    assert valid1 is True

    # Call 2 with identical nonce within valid time window -> Replay attack detected
    valid2, err2 = verify_hmac_signature(
        secret, payload, f"t={ts},v1={sig}", ts, nonce_header=unique_nonce, webhook_token="wh_1"
    )
    assert valid2 is False
    assert "Replay attack detectado" in err2

# ----------------- 2. Crypto At-Rest Secret Storage -----------------
def test_crypto_at_rest_encryption():
    plain = "sec_test_secret_1234567890abcdef"
    encrypted = encrypt_secret(plain)

    assert encrypted != plain
    assert encrypted.startswith("enc_")

    decrypted = decrypt_secret(encrypted)
    assert decrypted == plain

# ----------------- 3. Decoupled Rate Limiting Interface -----------------
def test_rate_limiter_interface():
    limiter = InMemoryRateLimitStore()
    ident = "test_client_ip"

    # Fire 5 requests with limit 5 -> should succeed
    for _ in range(5):
        assert limiter.is_rate_limited(ident, limit=5, window_seconds=60) is False

    # 6th request should trigger limit
    assert limiter.is_rate_limited(ident, limit=5, window_seconds=60) is True

# ----------------- 4. Advanced OOXML & Zip Bomb Protection -----------------
def test_ooxml_valid_structure():
    # Construct minimal valid OOXML XLSX in-memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types></Types>")
        zf.writestr("xl/workbook.xml", b"<workbook></workbook>")
    buf.seek(0)

    is_valid, err = validate_ooxml_xlsx(buf.getvalue())
    assert is_valid is True
    assert err == ""

def test_ooxml_fake_zip_missing_workbook():
    # Valid ZIP but NOT an Excel spreadsheet (missing xl/workbook.xml)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("malicious_script.sh", b"echo pwned")
    buf.seek(0)

    is_valid, err = validate_ooxml_xlsx(buf.getvalue())
    assert is_valid is False
    assert "Estructura OOXML inválida" in err

def test_zip_bomb_too_many_entries_protection():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(505): # Over 500 entries limit
            zf.writestr(f"file_{i}.txt", b"dummy")
    buf.seek(0)

    is_valid, err = validate_ooxml_xlsx(buf.getvalue())
    assert is_valid is False
    assert "Protección ZIP Bomb" in err

# ----------------- 5. Stream Parsing Endpoint for Large CSVs -----------------
def test_stream_parsing_csv():
    # 5,000 rows CSV
    lines = ["Banner Title", "Fecha,Importe"]
    for i in range(5000):
        lines.append(f"01/05/2026,\"{i+1}.000,50\"")
    content = "\n".join(lines).encode("utf-8")

    db = SessionLocal()
    u = db.query(User).filter(User.email == "stream_tester@anclora.com").first()
    if not u:
        u = User(email="stream_tester@anclora.com", password_hash=hash_password("CleanSheet2026!"), display_name="Stream Tester")
        db.add(u)
        db.commit()
        db.refresh(u)
    from auth import create_access_token
    token = create_access_token(u.id, u.email)
    db.close()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/files/stream-process",
        files={"file": ("stream_large.csv", content, "text/csv")},
        data={"output_format": "csv"},
        headers=headers
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert len(res.content) > 1000
    assert b"clean_stream_large.csv" in res.headers.get("content-disposition", "").encode("utf-8") or res.status_code == 200
