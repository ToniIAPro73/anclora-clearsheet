"""Anclora CleanSheet - Backend API tests"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@anclora.com"
DEMO_PASSWORD = "CleanSheet2026!"


@pytest.fixture(scope="module")
def anon_client():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def auth_client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


# ---------- Health ----------
def test_status(anon_client):
    r = anon_client.get(f"{API}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


# ---------- Auth ----------
def test_login_demo():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == DEMO_EMAIL
    # HttpOnly cookies should be present
    assert "access_token" in s.cookies or any(c.name == "access_token" for c in s.cookies)


def test_login_invalid():
    r = requests.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_auth_me(auth_client):
    r = auth_client.get(f"{API}/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == DEMO_EMAIL


def test_register_and_logout():
    s = requests.Session()
    email = f"test_user_{os.urandom(4).hex()}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123!", "display_name": "TEST User"})
    assert r.status_code == 200, r.text
    # Duplicate email
    r2 = requests.post(f"{API}/auth/register", json={"email": email, "password": "TestPass123!"})
    assert r2.status_code == 400
    # Logout
    r3 = s.post(f"{API}/auth/logout")
    assert r3.status_code == 200


# ---------- Sample dataset + analysis ----------
@pytest.fixture(scope="module")
def erp_file_id(anon_client):
    r = anon_client.get(f"{API}/samples/erp")
    assert r.status_code == 200
    return r.json()["file_id"]


def test_sample_erp(erp_file_id):
    assert erp_file_id


def test_analyze_erp(anon_client, erp_file_id):
    r = anon_client.get(f"{API}/files/{erp_file_id}/analyze")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "analysis" in body
    assert "original_preview" in body
    assert "normalized_preview" in body
    assert "python_script" in body
    analysis = body["analysis"]
    # Should propose default rules
    assert "default_rules" in analysis
    assert "recipe_yaml" in analysis
    # Should detect European decimal (comma decimal, dot thousands) in ERP data
    rules = analysis["default_rules"]
    assert "decimal_separator" in rules or "columns" in analysis
    # Title banner should be detected (first row is title)
    assert rules.get("remove_top_rows", 0) >= 1


# ---------- Preview interactive recalculation ----------
def test_preview_recalc(anon_client, erp_file_id):
    # First analyze to get default rules
    r = anon_client.get(f"{API}/files/{erp_file_id}/analyze")
    default_rules = r.json()["analysis"]["default_rules"]
    # Post to preview endpoint
    r2 = anon_client.post(f"{API}/files/preview", json={"file_id": erp_file_id, "rules": default_rules})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "preview" in body
    assert "recipe_yaml" in body
    assert "python_script" in body
    assert isinstance(body["python_script"], str) and "import pandas" in body["python_script"].lower() or "pandas" in body["python_script"]


# ---------- Export ----------
def test_export_xlsx(anon_client, erp_file_id):
    r = anon_client.get(f"{API}/files/{erp_file_id}/analyze")
    rules = r.json()["analysis"]["default_rules"]
    r2 = anon_client.post(f"{API}/files/export?format=xlsx", json={"file_id": erp_file_id, "rules": rules})
    assert r2.status_code == 200, r2.text
    assert len(r2.content) > 100
    ct = r2.headers.get("content-type", "")
    assert "spreadsheet" in ct or "octet" in ct


def test_export_csv(anon_client, erp_file_id):
    r = anon_client.get(f"{API}/files/{erp_file_id}/analyze")
    rules = r.json()["analysis"]["default_rules"]
    r2 = anon_client.post(f"{API}/files/export?format=csv", json={"file_id": erp_file_id, "rules": rules})
    assert r2.status_code == 200
    assert len(r2.content) > 10


# ---------- Recipes CRUD (authenticated) ----------
def test_recipes_crud(auth_client, erp_file_id):
    # Get analysis to build a recipe
    r = auth_client.get(f"{API}/files/{erp_file_id}/analyze")
    assert r.status_code == 200
    analysis = r.json()["analysis"]

    # Create
    payload = {
        "name": "TEST_ERP_Recipe",
        "description": "Test recipe",
        "recipe_yaml": analysis["recipe_yaml"],
        "structure_fingerprint": analysis.get("structure_fingerprint"),
        "source_format": "xlsx"
    }
    r_create = auth_client.post(f"{API}/recipes", json=payload)
    assert r_create.status_code == 200, r_create.text
    recipe = r_create.json()
    recipe_id = recipe["id"]
    assert recipe["name"] == "TEST_ERP_Recipe"

    # List
    r_list = auth_client.get(f"{API}/recipes")
    assert r_list.status_code == 200
    assert any(x["id"] == recipe_id for x in r_list.json())

    # Get
    r_get = auth_client.get(f"{API}/recipes/{recipe_id}")
    assert r_get.status_code == 200
    assert r_get.json()["id"] == recipe_id

    # Validate compatibility with same file
    r_val = auth_client.post(f"{API}/recipes/validate-compatibility", json={"recipe_id": recipe_id, "file_id": erp_file_id})
    assert r_val.status_code == 200, r_val.text
    assert "compatibility" in r_val.json()

    # Delete
    r_del = auth_client.delete(f"{API}/recipes/{recipe_id}")
    assert r_del.status_code == 200

    # Verify gone
    r_get2 = auth_client.get(f"{API}/recipes/{recipe_id}")
    assert r_get2.status_code == 404


def test_recipes_requires_auth():
    r = requests.get(f"{API}/recipes")
    assert r.status_code == 401


# ---------- Upload real file ----------
def test_upload_csv(anon_client):
    csv_data = b"col1,col2\n1,2\n3,4\n"
    files = {"file": ("test.csv", io.BytesIO(csv_data), "text/csv")}
    r = anon_client.post(f"{API}/files/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "file_id" in body



# ---------- Batch Processing ----------
def _make_messy_csv(name="msg.csv"):
    data = (
        b"INFORME DE VENTAS MENSUAL ERP - SAGE / SAP,,,,\n"
        b"Generado el:,01/02/2026,Departamento:,Finanzas,\n"
        b",,,,\n"
        b"Fecha Factura,ID Cliente,Cliente,Importe Neto,IVA 21%\n"
        b"01/05/2026,CLI-9012,Acme Iberica SL,\"1.250,50\",\"262,60\"\n"
        b"02/05/2026,CLI-4431,Logistica Global,\"3.400,00\",\"714,00\"\n"
    )
    return (name, io.BytesIO(data), "text/csv")


def test_batch_process_and_zip_download(anon_client):
    files = [
        ("files", _make_messy_csv("batch_a.csv")),
        ("files", _make_messy_csv("batch_b.csv")),
    ]
    r = anon_client.post(f"{API}/batch/process", files=files, data={"output_format": "xlsx"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_files"] == 2
    assert len(body["results"]) == 2
    for item in body["results"]:
        assert "clean_" in item["clean_name"]
        assert item["rows_in"] >= 1
        assert "storage_key" in item
    assert "zip_storage_key" in body
    assert body["zip_download_url"].startswith("/api/batch/download/")

    # Download the ZIP
    zip_key = body["zip_storage_key"]
    r2 = anon_client.get(f"{API}/batch/download/{zip_key}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("application/zip")
    # Verify it's a real zip and contains expected files
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(r2.content))
    names = zf.namelist()
    assert any("clean_batch_a" in n for n in names)
    assert any("clean_batch_b" in n for n in names)


def test_batch_download_not_found(anon_client):
    r = anon_client.get(f"{API}/batch/download/nonexistent_key_xxx.zip")
    assert r.status_code == 404


# ---------- Automations & Webhook Drop ----------
@pytest.fixture(scope="module")
def saved_recipe(auth_client, erp_file_id):
    r = auth_client.get(f"{API}/files/{erp_file_id}/analyze")
    analysis = r.json()["analysis"]
    payload = {
        "name": "TEST_Auto_Recipe",
        "recipe_yaml": analysis["recipe_yaml"],
        "structure_fingerprint": analysis.get("structure_fingerprint"),
        "source_format": "xlsx",
    }
    r = auth_client.post(f"{API}/recipes", json=payload)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    yield rid
    # cleanup
    auth_client.delete(f"{API}/recipes/{rid}")


def test_automations_requires_auth():
    r = requests.get(f"{API}/automations")
    assert r.status_code == 401
    r2 = requests.post(f"{API}/automations", json={"name": "x", "recipe_id": "x"})
    assert r2.status_code == 401


def test_create_list_delete_automation_and_webhook_drop(auth_client, saved_recipe):
    # Create
    payload = {
        "name": "TEST_Webhook_ERP",
        "recipe_id": saved_recipe,
        "schedule": "on_webhook",
        "target_format": "xlsx",
    }
    r = auth_client.post(f"{API}/automations", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "TEST_Webhook_ERP"
    assert body["token"].startswith("wh_")
    assert body["webhook_url"].startswith("/api/webhooks/drop/")
    token = body["token"]
    automation_id = body["id"]

    # List
    r2 = auth_client.get(f"{API}/automations")
    assert r2.status_code == 200
    items = r2.json()
    assert any(a["id"] == automation_id and a["token"] == token for a in items)

    # Webhook drop (public - no auth required)
    files = {"file": _make_messy_csv("hook_input.csv")}
    r3 = requests.post(f"{API}/webhooks/drop/{token}", files=files)
    assert r3.status_code == 200, r3.text
    ct = r3.headers.get("content-type", "")
    assert "spreadsheet" in ct or "octet" in ct or "xml" in ct
    assert len(r3.content) > 100

    # Verify runs_count incremented
    r4 = auth_client.get(f"{API}/automations")
    updated = [a for a in r4.json() if a["id"] == automation_id][0]
    assert updated["runs_count"] >= 1

    # Invalid webhook token
    r5 = requests.post(f"{API}/webhooks/drop/wh_invalid_xxx", files={"file": _make_messy_csv("x.csv")})
    assert r5.status_code == 404

    # Delete
    r6 = auth_client.delete(f"{API}/automations/{automation_id}")
    assert r6.status_code == 200

    # After delete, webhook token should no longer be usable
    r7 = requests.post(f"{API}/webhooks/drop/{token}", files={"file": _make_messy_csv("x.csv")})
    assert r7.status_code == 404
