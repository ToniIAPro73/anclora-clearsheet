import pytest
import io
from fastapi.testclient import TestClient
from server import app
from storage import storage
from models import SessionLocal, User
from auth import hash_password

client = TestClient(app)

@pytest.fixture
def auth_client():
    db = SessionLocal()
    u = db.query(User).filter(User.email == "storage_test@anclora.com").first()
    if not u:
        u = User(email="storage_test@anclora.com", password_hash=hash_password("CleanSheet2026!"), display_name="Storage User")
        db.add(u)
        db.commit()
    db.close()
    c = TestClient(app)
    c.post("/api/auth/login", json={"email": "storage_test@anclora.com", "password": "CleanSheet2026!"})
    return c

def test_request_direct_upload_credentials(auth_client):
    res = auth_client.post(
        "/api/storage/direct-upload-url",
        json={"filename": "direct_large.csv", "content_type": "text/csv"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "upload_url" in data
    assert "storage_key" in data
    assert data["storage_key"].endswith(".csv")

def test_direct_upload_stream_and_process(auth_client):
    # 1. Request signed direct upload URL
    cred_res = auth_client.post(
        "/api/storage/direct-upload-url",
        json={"filename": "browser_direct.csv", "content_type": "text/csv"}
    )
    assert cred_res.status_code == 200
    creds = cred_res.json()
    upload_url = creds["upload_url"]
    storage_key = creds["storage_key"]

    # 2. Browser directly streams bytes to upload URL
    csv_payload = b"Banner Title\nFecha,Importe\n01/05/2026,\"1.250,50\"\n02/05/2026,\"3.400,00\"\n"
    put_res = client.put(upload_url, content=csv_payload, headers={"Content-Type": "text/csv"})
    assert put_res.status_code == 200
    assert put_res.json()["status"] == "uploaded"
    assert put_res.json()["bytes_written"] == len(csv_payload)

    # 3. Verify file stored in private storage
    stored_path = storage.get_file_path(storage_key)
    with open(stored_path, "rb") as f:
        assert f.read() == csv_payload
