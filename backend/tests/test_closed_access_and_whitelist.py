import os
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_ADMIN_EMAILS"] = "admin@anclora.local"
os.environ["AUTH_PASSWORD_MIN_LENGTH"] = "12"

from server import app
from models import SessionLocal, User, AuthWhitelist, AuthAuditEvent
from auth import hash_password, hash_token, generate_raw_token

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

@pytest.fixture
def admin_user(db_session):
    admin = db_session.query(User).filter(User.email == "admin@anclora.local").first()
    if not admin:
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@anclora.local",
            password_hash=hash_password("AdminSecurePassword123!"),
            display_name="Admin",
            status="active"
        )
        db_session.add(admin)
        db_session.flush()

        wl = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="admin@anclora.local",
            status="active",
            user_id=admin.id,
            created_by="system",
            activated_at=datetime.now(timezone.utc)
        )
        db_session.add(wl)
        db_session.commit()
    return admin

def test_public_registration_disabled(client):
    r = client.post("/api/auth/register", json={"email": "hacker@evil.com", "password": "password12345"})
    assert r.status_code == 403
    assert "deshabilitado" in r.text.lower() or "invitación" in r.text.lower()

def test_whitelist_admin_authorization(client, admin_user):
    # Unauthenticated request to /api/auth/whitelist -> 401
    r = client.post("/api/auth/whitelist", json={"email": "newuser@corp.com"})
    assert r.status_code == 401

    # Login as admin
    login_res = client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    assert login_res.status_code == 200

    # Admin adds email to whitelist
    invited_email = f"invited_{uuid.uuid4().hex[:6]}@anclora.com"
    r = client.post("/api/auth/whitelist", json={"email": invited_email})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == invited_email
    assert data["status"] == "pending"
    assert "activation_token" in data
    raw_token = data["activation_token"]

    # Verify DB stores SHA-256 only, NOT raw token
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelist).filter(AuthWhitelist.email == invited_email).first()
        assert entry is not None
        assert entry.token_hash == hash_token(raw_token)
        assert raw_token not in entry.token_hash
        assert len(entry.token_hash) == 64
    finally:
        db.close()

def test_whitelist_duplicate_handling(client, admin_user):
    client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    dup_email = f"dup_{uuid.uuid4().hex[:6]}@anclora.com"
    # Add email
    r1 = client.post("/api/auth/whitelist", json={"email": dup_email})
    assert r1.status_code == 200

    # Add again while pending -> refreshes token
    r2 = client.post("/api/auth/whitelist", json={"email": dup_email})
    assert r2.status_code == 200
    assert r2.json()["activation_token"] != r1.json()["activation_token"]

def test_token_expiry_validation(client, db_session):
    # Create expired whitelist entry
    expired_email = f"expired_{uuid.uuid4().hex[:6]}@anclora.com"
    expired_raw = generate_raw_token()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    entry = AuthWhitelist(
        id=str(uuid.uuid4()),
        email=expired_email,
        status="pending",
        token_hash=hash_token(expired_raw),
        expires_at=past,
        created_by="admin"
    )
    db_session.add(entry)
    db_session.commit()

    # Validate expired token -> 400
    r = client.get(f"/api/auth/activation/validate?token={expired_raw}")
    assert r.status_code == 400
    assert "expirada" in r.text.lower() or "no válida" in r.text.lower()

def test_one_time_activation_and_password_minimum(client, db_session):
    act_email = f"activate_{uuid.uuid4().hex[:6]}@anclora.com"
    raw_token = generate_raw_token()
    entry = AuthWhitelist(
        id=str(uuid.uuid4()),
        email=act_email,
        status="pending",
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_by="admin"
    )
    db_session.add(entry)
    db_session.commit()

    # 1. Validation check
    val_res = client.get(f"/api/auth/activation/validate?token={raw_token}")
    assert val_res.status_code == 200
    assert val_res.json()["valid"] is True
    assert val_res.json()["email"] == act_email

    # 2. Password < 12 characters -> rejected
    short_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": "short",
        "display_name": "Short Pwd"
    })
    assert short_res.status_code == 400
    assert "12" in short_res.text

    # 3. Valid activation
    act_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": "StrongPassword2026!#",
        "display_name": "Active User"
    })
    assert act_res.status_code == 200
    user_data = act_res.json()
    assert user_data["email"] == act_email

    # 4. Token reuse attempt -> rejected
    reuse_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": "AnotherPassword2026!#",
        "display_name": "Imposter"
    })
    assert reuse_res.status_code == 400

    # 5. Session cookies check
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is True
    assert me_res.json()["user"]["email"] == act_email

def test_login_success_and_generic_failure(client, db_session):
    login_email = f"login_{uuid.uuid4().hex[:6]}@anclora.com"
    pwd = "StrongPassword2026!#"
    user = User(
        id=str(uuid.uuid4()),
        email=login_email,
        password_hash=hash_password(pwd),
        display_name="Login Tester",
        status="active"
    )
    db_session.add(user)
    db_session.commit()

    # Valid login
    r_ok = client.post("/api/auth/login", json={
        "email": login_email,
        "password": pwd
    })
    assert r_ok.status_code == 200

    # Wrong password -> generic error
    r_wrong = client.post("/api/auth/login", json={
        "email": login_email,
        "password": "wrongpassword"
    })
    assert r_wrong.status_code == 401
    assert "credenciales incorrectas" in r_wrong.text.lower()

    # Non-existent email -> same generic error (prevent user enumeration)
    r_none = client.post("/api/auth/login", json={
        "email": f"nonexistent_{uuid.uuid4().hex[:6]}@anclora.com",
        "password": pwd
    })
    assert r_none.status_code == 401
    assert "credenciales incorrectas" in r_none.text.lower()

def test_disabled_user_and_revoked_whitelist(client, db_session):
    rev_email = f"rev_{uuid.uuid4().hex[:6]}@anclora.com"
    pwd = "StrongPassword2026!#"
    user = User(
        id=str(uuid.uuid4()),
        email=rev_email,
        password_hash=hash_password(pwd),
        display_name="Revoked Tester",
        status="active"
    )
    db_session.add(user)
    db_session.commit()

    entry = db_session.query(AuthWhitelist).filter(AuthWhitelist.email == rev_email).first()
    assert entry is not None

    # Log in as user to establish session
    r_login = client.post("/api/auth/login", json={"email": rev_email, "password": pwd})
    assert r_login.status_code == 200

    # Log in as admin and revoke user
    client_admin = TestClient(app)
    r_adm_login = client_admin.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    assert r_adm_login.status_code == 200

    # Revoke via admin endpoint
    rev_res = client_admin.post(f"/api/auth/whitelist/{entry.id}/revoke")
    assert rev_res.status_code == 200

    # Original user's active session is now invalid on /api/auth/me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is False

    # New login attempt by revoked user -> generic 401
    r_rev = client.post("/api/auth/login", json={
        "email": rev_email,
        "password": pwd
    })
    assert r_rev.status_code == 401
    assert "credenciales incorrectas" in r_rev.text.lower()

def test_whitelist_list_never_leaks_tokens(client, admin_user):
    client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    r = client.get("/api/auth/whitelist")
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    for item in items:
        assert "token_hash" not in item
        assert "token" not in item
        assert "password" not in item
