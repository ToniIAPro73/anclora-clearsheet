import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timezone
from server import app
from models import SessionLocal, User, Recipe, ExternalStorageConnection, Execution, AuthWhitelist
from auth import hash_password

client = TestClient(app)

@pytest.fixture
def auth_headers_user1():
    db = SessionLocal()
    user1 = db.query(User).filter(User.email == "user1_cloud@example.com").first()
    if not user1:
        user1 = User(
            email="user1_cloud@example.com",
            password_hash=hash_password("PassUser1_2026!"),
            display_name="User 1 Cloud",
            status="active"
        )
        db.add(user1)
        db.flush()
    wl1 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "user1_cloud@example.com").first()
    if not wl1:
        wl1 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="user1_cloud@example.com",
            status="active",
            user_id=user1.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl1)
    else:
        wl1.user_id = user1.id
        wl1.status = "active"
    db.commit()
    db.close()

    res = client.post("/api/auth/login", json={"email": "user1_cloud@example.com", "password": "PassUser1_2026!"})
    assert res.status_code == 200
    cookies = res.cookies
    return {"Cookie": f"access_token={cookies.get('access_token')}"}

@pytest.fixture
def auth_headers_user2():
    db = SessionLocal()
    user2 = db.query(User).filter(User.email == "user2_cloud@example.com").first()
    if not user2:
        user2 = User(
            email="user2_cloud@example.com",
            password_hash=hash_password("PassUser2_2026!"),
            display_name="User 2 Cloud",
            status="active"
        )
        db.add(user2)
        db.flush()
    wl2 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "user2_cloud@example.com").first()
    if not wl2:
        wl2 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="user2_cloud@example.com",
            status="active",
            user_id=user2.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl2)
    else:
        wl2.user_id = user2.id
        wl2.status = "active"
    db.commit()
    db.close()

    res = client.post("/api/auth/login", json={"email": "user2_cloud@example.com", "password": "PassUser2_2026!"})
    assert res.status_code == 200
    cookies = res.cookies
    return {"Cookie": f"access_token={cookies.get('access_token')}"}

@patch("boto3.client")
def test_create_and_list_connection_no_secret_leaks(mock_boto, auth_headers_user1):
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    # 1. Test unsaved connection
    test_res = client.post("/api/connectors/test", json={
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "client-raw-data",
            "access_key_id": "AKIA9876543210XYZ",
            "secret_access_key": "SUPER_SECRET_VALUE_NEVER_LEAK",
            "region_name": "eu-central-1"
        }
    })
    assert test_res.status_code == 200
    assert test_res.json()["success"] is True

    # 2. Create connection
    create_res = client.post("/api/connectors", headers=auth_headers_user1, json={
        "name": "AWS S3 Facturación Clientes",
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "client-raw-data",
            "access_key_id": "AKIA9876543210XYZ",
            "secret_access_key": "SUPER_SECRET_VALUE_NEVER_LEAK",
            "region_name": "eu-central-1"
        }
    })
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["name"] == "AWS S3 Facturación Clientes"
    assert "SUPER_SECRET_VALUE_NEVER_LEAK" not in str(created)
    assert created["config_preview"]["access_key_preview"].startswith("AKIA...")
    conn_id = created["id"]

    # 3. List connections
    list_res = client.get("/api/connectors", headers=auth_headers_user1)
    assert list_res.status_code == 200
    conns = list_res.json()
    assert any(c["id"] == conn_id for c in conns)
    # Strict verification: secret key never in response
    assert "SUPER_SECRET_VALUE_NEVER_LEAK" not in str(conns)

@patch("boto3.client")
def test_multitenant_connection_isolation(mock_boto, auth_headers_user1, auth_headers_user2):
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    # Create connection for user 1
    create_res = client.post("/api/connectors", headers=auth_headers_user1, json={
        "name": "User 1 Private Storage",
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "user1-private-vault",
            "access_key_id": "AKIAUSER1PRIVATE",
            "secret_access_key": "SECRET111",
            "region_name": "us-east-1"
        }
    })
    conn_id = create_res.json()["id"]

    # User 2 tries to list objects of User 1 connection -> 404 forbidden
    res = client.get(f"/api/connectors/{conn_id}/objects", headers=auth_headers_user2)
    assert res.status_code == 404

    # User 2 tries to test User 1 connection -> 404 forbidden
    res = client.post(f"/api/connectors/{conn_id}/test", headers=auth_headers_user2)
    assert res.status_code == 404

    # User 2 tries to delete User 1 connection -> 404 forbidden
    res = client.delete(f"/api/connectors/{conn_id}", headers=auth_headers_user2)
    assert res.status_code == 404

@patch("boto3.client")
def test_cloud_pipeline_execution_s3_to_s3(mock_boto, auth_headers_user1):
    mock_s3 = MagicMock()
    # Mock remote CSV file in S3
    csv_bytes = b"Fecha,Importe,Cliente\n01/02/2026,1.250,50,Empresa SL\n02/02/2026,300,00,Tech SA\n"
    mock_body = MagicMock()
    mock_body.read.side_effect = [csv_bytes, b""]
    mock_s3.get_object.return_value = {"Body": mock_body}
    mock_s3.head_object.return_value = {
        "ContentLength": len(csv_bytes),
        "ETag": '"source-etag"',
        "ContentType": "text/csv"
    }
    mock_s3.put_object.return_value = {"ETag": '"target-normalized-etag"'}
    mock_boto.return_value = mock_s3

    # 1. Create S3 Connection
    create_res = client.post("/api/connectors", headers=auth_headers_user1, json={
        "name": "Pipeline S3 Connector",
        "provider_type": "s3_compatible",
        "s3_config": {
            "bucket_name": "production-lake",
            "access_key_id": "AKIA_PROD_12345",
            "secret_access_key": "SECRET_PROD_54321",
            "region_name": "us-east-1"
        }
    })
    conn_id = create_res.json()["id"]

    # 2. Create Recipe for user1
    recipe_yaml = """
version: '1.0'
rules:
  remove_top_rows: 0
  decimal_separator: ','
  thousands_separator: '.'
  date_output_format: 'YYYY-MM-DD'
columns:
  Fecha:
    type: date
  Importe:
    type: numeric
  Cliente:
    type: text
column_aliases:
  Importe:
    - Amount
    - Total
"""
    rec_res = client.post("/api/recipes", headers=auth_headers_user1, json={
        "name": "Cloud Normalizer Recipe",
        "recipe_yaml": recipe_yaml,
        "source_format": "csv"
    })
    recipe_id = rec_res.json()["id"]

    # 3. Execute Cloud Pipeline (Source S3 -> RecipeExecutionService -> Target S3)
    pipeline_res = client.post("/api/connectors/execute-pipeline", headers=auth_headers_user1, json={
        "source_connection_id": conn_id,
        "source_key": "raw/sales_input.csv",
        "recipe_id": recipe_id,
        "target_key": "normalized/sales_output.csv",
        "output_format": "csv"
    })

    assert pipeline_res.status_code == 200
    data = pipeline_res.json()
    assert data["status"] == "completed"
    assert data["source"]["key"] == "raw/sales_input.csv"
    assert data["target"]["key"] == "normalized/sales_output.csv"
    assert data["rows_in"] == 3
    assert data["rows_out"] == 2
    assert data["target"]["etag"] == "target-normalized-etag"

    # Verify execution registered in Execution table
    db = SessionLocal()
    exec_row = db.query(Execution).filter(Execution.id == data["execution_id"]).first()
    assert exec_row is not None
    assert "[CLOUD]" in exec_row.file_name
    assert exec_row.result_metadata["pipeline_type"] == "cloud_s3_to_s3"
    db.close()
