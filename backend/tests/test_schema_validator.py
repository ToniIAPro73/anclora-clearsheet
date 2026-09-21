import pytest
from schema_validator import SchemaCompatibilityService

def test_compatible_schema():
    recipe = {
        "structure_fingerprint": "fp123",
        "columns": {
            "Fecha": {"type": "date"},
            "Cliente": {"type": "text"},
            "Importe": {"type": "decimal"}
        }
    }
    candidate = {
        "structure_fingerprint": "fp123",
        "columns": [
            {"name": "Fecha", "detected_type": "date"},
            {"name": "Cliente", "detected_type": "text"},
            {"name": "Importe", "detected_type": "decimal"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "compatible"
    assert res["is_blocking"] is False
    assert len(res["missing_columns"]) == 0

def test_warning_added_columns_schema():
    recipe = {
        "columns": {
            "Fecha": {"type": "date"},
            "Importe": {"type": "decimal"}
        }
    }
    candidate = {
        "columns": [
            {"name": "Fecha", "detected_type": "date"},
            {"name": "Importe", "detected_type": "decimal"},
            {"name": "NuevaColumnaExtra", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "warning"
    assert res["is_blocking"] is False
    assert "NuevaColumnaExtra" in res["added_columns"]

def test_blocking_missing_required_columns():
    recipe = {
        "columns": {
            "Fecha": {"type": "date"},
            "Cliente": {"type": "text"},
            "Importe": {"type": "decimal"},
            "IVA": {"type": "decimal"}
        }
    }
    # File only has 1 matching column -> blocking!
    candidate = {
        "columns": [
            {"name": "Fecha", "detected_type": "date"},
            {"name": "Comentario", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "blocking"
    assert res["is_blocking"] is True
    assert "Cliente" in res["missing_columns"]

def test_type_drift_warning():
    recipe = {
        "columns": {
            "Fecha": {"type": "date"},
            "Importe": {"type": "decimal"}
        }
    }
    # Importe changed from decimal to text
    candidate = {
        "columns": [
            {"name": "Fecha", "detected_type": "date"},
            {"name": "Importe", "detected_type": "text"}
        ]
    }
    res = SchemaCompatibilityService.evaluate(recipe, candidate)
    assert res["status"] == "warning"
    assert any(td["column"] == "Importe" and td["actual_type"] == "text" for td in res["type_drifts"])
