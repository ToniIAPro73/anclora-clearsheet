import pytest
from fastapi.testclient import TestClient
from server import app
from models import init_db, SessionLocal, User, Recipe, AutomationWebhook
from auth import hash_password
from schema_validator import SchemaCompatibilityService

init_db()
client = TestClient(app)

# ----------------- 1. Column Aliasing Unit Tests -----------------
def test_alias_resolution_single_clean_match():
    recipe = {
        "columns": {
            "customer_id": {"type": "text"},
            "amount": {"type": "decimal"}
        },
        "column_aliases": {
            "customer_id": ["codigo_cliente", "client_id", "customer_code"]
        }
    }
    candidate = {
        "columns": [
            {"name": "codigo_cliente", "detected_type": "text"},
            {"name": "amount", "detected_type": "decimal"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "compatible"
    assert res["is_blocking"] is False
    assert res["applied_aliases"] == {"codigo_cliente": "customer_id"}
    assert "customer_id" in res["matched_columns"]

def test_alias_ambiguity_multiple_matches_warning():
    recipe = {
        "columns": {
            "customer_id": {"type": "text"}
        },
        "column_aliases": {
            "customer_id": ["codigo_cliente", "client_id"]
        }
    }
    # Candidate contains BOTH aliases! Ambiguity -> warning
    candidate = {
        "columns": [
            {"name": "codigo_cliente", "detected_type": "text"},
            {"name": "client_id", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "warning"
    assert any("Ambigüedad de alias" in item["message_es"] for item in res["drift_items"])

def test_alias_conflict_two_candidates_same_canonical():
    recipe = {
        "columns": {
            "customer_id": {"type": "text"},
            "account_id": {"type": "text"}
        },
        "column_aliases": {
            "customer_id": ["code_id"],
            "account_id": ["code_id"] # Collision!
        }
    }
    candidate = {
        "columns": [
            {"name": "code_id", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "warning"
    assert any("Conflicto de alias" in item["message_es"] for item in res["drift_items"])

def test_alias_with_type_mismatch():
    recipe = {
        "columns": {
            "fecha_factura": {"type": "date"}
        },
        "column_aliases": {
            "fecha_factura": ["fecha", "invoice_date"]
        }
    }
    # Candidate matches alias but detected type is text instead of date
    candidate = {
        "columns": [
            {"name": "fecha", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "warning"
    assert any(td["column"] == "fecha_factura" and td["actual_type"] == "text" for td in res["type_drifts"])

# ----------------- 2. Webhook Execution Inspector & User Isolation -----------------
def test_webhook_execution_inspector_and_isolation():
    import uuid
    from datetime import datetime, timezone
    from models import AuthWhitelist
    db = SessionLocal()
    u1 = db.query(User).filter(User.email == "user1_insp@test.com").first()
    if not u1:
        u1 = User(email="user1_insp@test.com", password_hash=hash_password("Pass1!"), display_name="User 1", status="active")
        db.add(u1)
        db.flush()
    wl1 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "user1_insp@test.com").first()
    if not wl1:
        wl1 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="user1_insp@test.com",
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

    u2 = db.query(User).filter(User.email == "user2_insp@test.com").first()
    if not u2:
        u2 = User(email="user2_insp@test.com", password_hash=hash_password("Pass1!"), display_name="User 2", status="active")
        db.add(u2)
        db.flush()
    wl2 = db.query(AuthWhitelist).filter(AuthWhitelist.email == "user2_insp@test.com").first()
    if not wl2:
        wl2 = AuthWhitelist(
            id=str(uuid.uuid4()),
            email="user2_insp@test.com",
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

    rec1 = db.query(Recipe).filter(Recipe.user_id == u1.id, Recipe.name == "Recipe Insp").first()
    if not rec1:
        rec1 = Recipe(
            user_id=u1.id,
            name="Recipe Insp",
            definition_yaml="""
recipe_version: "1.0"
columns:
  customer_id:
    type: text
column_aliases:
  customer_id: ["client_code"]
rules:
  remove_top_rows: 0
"""
        )
        db.add(rec1)
        db.commit()
        db.refresh(rec1)

    wh1 = db.query(AutomationWebhook).filter(AutomationWebhook.user_id == u1.id).first()
    if not wh1:
        wh1 = AutomationWebhook(
            user_id=u1.id,
            recipe_id=rec1.id,
            name="WH Insp",
            token="wh_token_insp_1",
            secret_key="sec_insp_key",
            target_format="xlsx"
        )
        db.add(wh1)
        db.commit()
        db.refresh(wh1)

    wh1_id = wh1.id
    wh1_token = wh1.token
    db.close()

    # User 2 logs in and tries to inspect User 1's webhook -> 404/403 Isolated
    client_u2 = TestClient(app)
    login2 = client_u2.post("/api/auth/login", json={"email": "user2_insp@test.com", "password": "Pass1!"})
    assert login2.status_code == 200
    token_u2 = login2.cookies.get("access_token")

    res_iso = client_u2.get(f"/api/automations/{wh1_id}/executions", headers={"Authorization": f"Bearer {token_u2}"})
    assert res_iso.status_code in [403, 404]

    # Post a file to User 1's webhook using aliased column 'client_code'
    csv_payload = b"client_code\nCLI-9999\n"
    post_res = client.post(f"/api/webhooks/drop/{wh1_token}", files={"file": ("drop_aliased.csv", csv_payload, "text/csv")})
    assert post_res.status_code == 200

    # User 1 logs in and inspects their executions
    client_u1 = TestClient(app)
    login1 = client_u1.post("/api/auth/login", json={"email": "user1_insp@test.com", "password": "Pass1!"})
    assert login1.status_code == 200
    token_u1 = login1.cookies.get("access_token")

    res_u1 = client_u1.get(f"/api/automations/{wh1_id}/executions", headers={"Authorization": f"Bearer {token_u1}"})
    assert res_u1.status_code == 200
    data = res_u1.json()
    assert data["webhook_name"] == "WH Insp"
    assert len(data["executions"]) >= 1

    first_ex = data["executions"][0]
    assert first_ex["schema_compatibility"] == "compatible"
    assert first_ex["applied_aliases"] == {"client_code": "customer_id"}
    # Verify no raw cell values or secret keys are exposed
    assert "CLI-9999" not in str(first_ex)
    assert "sec_insp_key" not in str(first_ex)
