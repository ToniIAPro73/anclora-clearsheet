import pytest
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

EXPECTED_PUBLIC_ROUTES = [
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/files/upload"),
    ("GET", "/api/files/{file_id}/analyze"),
    ("POST", "/api/files/preview"),
    ("POST", "/api/files/export"),
    ("POST", "/api/files/stream-process"),
    ("POST", "/api/files/detect-dialect"),
    ("POST", "/api/recipes"),
    ("GET", "/api/recipes"),
    ("GET", "/api/recipes/{recipe_id}"),
    ("DELETE", "/api/recipes/{recipe_id}"),
    ("GET", "/api/recipes/{recipe_id}/aliases"),
    ("POST", "/api/recipes/{recipe_id}/aliases"),
    ("DELETE", "/api/recipes/{recipe_id}/aliases"),
    ("POST", "/api/recipes/validate-compatibility"),
    ("POST", "/api/batch/process"),
    ("GET", "/api/batch/download/{storage_key}"),
    ("GET", "/api/batch/executions"),
    ("GET", "/api/batch/executions/{execution_id}"),
    ("POST", "/api/automations"),
    ("GET", "/api/automations"),
    ("DELETE", "/api/automations/{automation_id}"),
    ("POST", "/api/automations/{automation_id}/regenerate-secret"),
    ("GET", "/api/automations/{automation_id}/executions"),
    ("POST", "/api/webhooks/drop/{token}"),
    ("POST", "/api/storage/direct-upload-url"),
    ("PUT", "/api/storage/direct-upload/{object_key}"),
    ("GET", "/api/executions"),
    ("GET", "/api/samples/{sample_type}"),
    ("GET", "/api/status"),
    ("POST", "/api/connectors/test"),
    ("POST", "/api/connectors"),
    ("GET", "/api/connectors"),
    ("DELETE", "/api/connectors/{connection_id}"),
    ("POST", "/api/connectors/{connection_id}/test"),
    ("GET", "/api/connectors/{connection_id}/objects"),
    ("POST", "/api/connectors/execute-pipeline"),
    ("POST", "/api/schedules"),
    ("GET", "/api/schedules"),
    ("GET", "/api/schedules/{schedule_id}"),
    ("PATCH", "/api/schedules/{schedule_id}"),
    ("DELETE", "/api/schedules/{schedule_id}"),
    ("POST", "/api/schedules/{schedule_id}/enable"),
    ("POST", "/api/schedules/{schedule_id}/disable"),
    ("POST", "/api/schedules/{schedule_id}/run-now"),
    ("GET", "/api/schedules/{schedule_id}/runs"),
    ("POST", "/api/schedules/preview-selector"),
]

def test_api_contract_routes_exist():
    registered_routes = {}
    for r in app.routes:
        if hasattr(r, "methods") and hasattr(r, "path"):
            for m in r.methods:
                registered_routes[(m, r.path)] = True

    for method, path in EXPECTED_PUBLIC_ROUTES:
        assert (method, path) in registered_routes, f"Missing route contract: {method} {path}"

def test_openapi_json_schema_generation():
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema
    assert "/api/status" in schema["paths"]
    assert "/api/auth/login" in schema["paths"]
    assert "/api/batch/process" in schema["paths"]
    assert "/api/webhooks/drop/{token}" in schema["paths"]
