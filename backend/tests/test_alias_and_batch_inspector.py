import pytest
from fastapi.testclient import TestClient
from server import app
from models import init_db, SessionLocal, User, Recipe, Execution
from auth import hash_password

init_db()
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_alias_and_batch_data():
    import uuid
    from datetime import datetime, timezone
    from models import AuthWhitelist
    db = SessionLocal()
    # User 1
    u1 = db.query(User).filter(User.email == "alias_u1@test.com").first()
    if not u1:
        u1 = User(email="alias_u1@test.com", password_hash=hash_password("Pass1!"), display_name="Alias U1", status="active")
        db.add(u1)
        db.flush()
    wl1 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "alias_u1@test.com").first()
    if not wl1:
        wl1 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="alias_u1@test.com",
            status="active",
            user_id=u1.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl1)
    else:
        wl1.user_id = u1.id
        wl1.status = "active"
    db.commit()
    db.refresh(u1)

    # User 2 (adversary for isolation tests)
    u2 = db.query(User).filter(User.email == "alias_u2@test.com").first()
    if not u2:
        u2 = User(email="alias_u2@test.com", password_hash=hash_password("Pass1!"), display_name="Alias U2", status="active")
        db.add(u2)
        db.flush()
    wl2 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "alias_u2@test.com").first()
    if not wl2:
        wl2 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="alias_u2@test.com",
            status="active",
            user_id=u2.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl2)
    else:
        wl2.user_id = u2.id
        wl2.status = "active"
    db.commit()
    db.refresh(u2)

    # Recipe for U1
    rec1 = Recipe(
        user_id=u1.id,
        name="Recipe Alias Test",
        recipe_version="1.0",
        definition_yaml="""
recipe_version: "1.0"
columns:
  customer_id:
    type: text
  invoice_total:
    type: decimal
column_aliases:
  customer_id: ["client_code"]
rules:
  remove_top_rows: 0
"""
    )
    db.add(rec1)
    db.commit()
    db.refresh(rec1)

    rec_id = str(rec1.id)
    u1_id = str(u1.id)
    u2_id = str(u2.id)
    db.close()

    return {
        "user1_id": u1_id,
        "user2_id": u2_id,
        "recipe_id": rec_id
    }

# ----------------- 1. Alias CRUD & Validation Tests -----------------
def test_alias_crud_operations(setup_alias_and_batch_data):
    rec_id = setup_alias_and_batch_data["recipe_id"]

    client_u1 = TestClient(app)
    login1 = client_u1.post("/api/auth/login", json={"email": "alias_u1@test.com", "password": "Pass1!"})
    assert login1.status_code == 200
    token1 = login1.cookies.get("access_token")
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 1. Get aliases
    res_get = client_u1.get(f"/api/recipes/{rec_id}/aliases", headers=headers1)
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "customer_id" in data_get["canonical_columns"]
    assert "client_code" in data_get["aliases"].get("customer_id", [])

    # 2. Add valid alias
    res_add = client_u1.post(
        f"/api/recipes/{rec_id}/aliases",
        json={"canonical_column": "customer_id", "alias": "cod_cliente"},
        headers=headers1
    )
    assert res_add.status_code == 200
    assert "cod_cliente" in res_add.json()["aliases"]["customer_id"]

    # 3. Validation: empty alias -> 400
    res_empty = client_u1.post(
        f"/api/recipes/{rec_id}/aliases",
        json={"canonical_column": "customer_id", "alias": "   "},
        headers=headers1
    )
    assert res_empty.status_code == 400

    # 4. Validation: canonical column as its own alias -> 400
    res_self = client_u1.post(
        f"/api/recipes/{rec_id}/aliases",
        json={"canonical_column": "customer_id", "alias": "customer_id"},
        headers=headers1
    )
    assert res_self.status_code == 400
    assert "no puede ser su propio alias" in res_self.json()["detail"]

    # 5. Validation: alias collision (alias already assigned to another canonical column) -> 400
    res_collision = client_u1.post(
        f"/api/recipes/{rec_id}/aliases",
        json={"canonical_column": "invoice_total", "alias": "client_code"},
        headers=headers1
    )
    assert res_collision.status_code == 400
    assert "Conflicto de alias" in res_collision.json()["detail"]

    # 6. Delete alias
    res_del = client_u1.request(
        "DELETE",
        f"/api/recipes/{rec_id}/aliases",
        json={"canonical_column": "customer_id", "alias": "cod_cliente"},
        headers=headers1
    )
    assert res_del.status_code == 200
    assert "cod_cliente" not in res_del.json()["aliases"].get("customer_id", [])

# ----------------- 2. Batch Inspector & User Isolation Tests -----------------
def test_batch_inspector_and_user_isolation(setup_alias_and_batch_data):
    rec_id = setup_alias_and_batch_data["recipe_id"]

    client_u1 = TestClient(app)
    login1 = client_u1.post("/api/auth/login", json={"email": "alias_u1@test.com", "password": "Pass1!"})
    token1 = login1.cookies.get("access_token")
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Run Batch with 2 files (1 clean with aliased column 'client_code', 1 bad file for partial failure)
    valid_csv = ("valid_alias.csv", b"client_code,invoice_total\nCLI-100,\"500,00\"\n", "text/csv")
    bad_csv = ("corrupt_format.xlsx", b"FAKE_NOT_A_REAL_ZIP", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    batch_res = client_u1.post(
        "/api/batch/process",
        files=[("files", valid_csv), ("files", bad_csv)],
        data={"recipe_id": rec_id, "output_format": "xlsx"},
        headers=headers1
    )
    assert batch_res.status_code == 200
    batch_data = batch_res.json()
    assert batch_data["successful_files"] == 1
    assert batch_data["failed_files"] == 1

    # List batch executions as User 1
    list_res = client_u1.get("/api/batch/executions", headers=headers1)
    assert list_res.status_code == 200
    batches = list_res.json()
    assert len(batches) >= 1

    batch_entry = batches[0]
    assert batch_entry["successful_count"] == 1
    assert batch_entry["failed_count"] == 1
    b_id = batch_entry["batch_id"]

    # Detail view as User 1
    detail_res = client_u1.get(f"/api/batch/executions/{b_id}", headers=headers1)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["manifest"]) == 2
    assert any(m["status"] == "failed" and m["original_name"] == "corrupt_format.xlsx" for m in detail["manifest"])
    assert any(m["status"] == "completed" and m["original_name"] == "valid_alias.csv" for m in detail["manifest"])

    # User 2 logs in and tries to access User 1's batch execution -> 404 Forbidden/Isolated
    client_u2 = TestClient(app)
    login2 = client_u2.post("/api/auth/login", json={"email": "alias_u2@test.com", "password": "Pass1!"})
    token2 = login2.cookies.get("access_token")
    headers2 = {"Authorization": f"Bearer {token2}"}

    res_iso = client_u2.get(f"/api/batch/executions/{b_id}", headers=headers2)
    assert res_iso.status_code == 404
