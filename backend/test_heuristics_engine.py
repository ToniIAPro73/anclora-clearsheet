import pytest
import os
import io
import pandas as pd
import yaml

from heuristics import HeuristicAnalyzer, generate_structure_fingerprint, check_recipe_compatibility
from engine import NormalizationPlanner, TransformationEngine

def test_title_rows_detection():
    # Messy table with 2 banner rows
    raw_rows = [
        ["INFORME FINANCIERO MENSUAL", "", "", ""],
        ["Fecha Emisión: 2026-02-01", "", "", ""],
        ["Fecha", "Cliente", "Importe", "Estado"],
        ["2026-02-02", "Cliente A", "100.50", "Pagado"],
        ["2026-02-03", "Cliente B", "250.00", "Pendiente"]
    ]
    detected_row, conf, reason = HeuristicAnalyzer.detect_title_rows(raw_rows)
    assert detected_row == 2
    assert conf >= 0.85

def test_multilevel_header_detection():
    raw_rows = [
        ["", "Ventas", "Ventas", "Costes", "Costes"],
        ["Fecha", "Neto", "IVA", "Neto", "IVA"],
        ["2026-01-01", "100", "21", "50", "10.5"]
    ]
    is_multi, num_rows, flattened = HeuristicAnalyzer.detect_multilevel_headers(raw_rows, 0)
    assert is_multi is True
    assert num_rows == 2
    assert "Ventas_Neto" in flattened or "Ventas_IVA" in flattened

def test_european_decimal_detection():
    values = ["1.234,50", "250,75", "10.000,00", "45,20"]
    result = HeuristicAnalyzer.detect_decimal_format(values)
    assert result["decimal_separator"] == ","
    assert result["thousands_separator"] == "."
    assert result["confidence"] > 0.8

def test_mixed_dates_and_ambiguity_detection():
    # 01/02/2026 is ambiguous (could be 1st Feb or 2nd Jan)
    values = ["01/02/2026", "05/03/2026", "11/04/2026"]
    result = HeuristicAnalyzer.detect_date_inconsistencies(values)
    assert result["is_date"] is True
    assert result["is_ambiguous"] is True

def test_deterministic_reproducibility():
    """
    Test reproducible recipe:
    File A cleaned -> Recipe R -> Recipe R applied to identical File B produces deterministic output
    """
    raw_rows_a = [
        ["TITULO INFORME", ""],
        ["Fecha", "Importe"],
        ["01/05/2026", "1.250,50"],
        ["02/05/2026", "3.400,00"]
    ]
    plan = NormalizationPlanner.plan(raw_rows_a)
    recipe_dict = yaml.safe_load(plan["recipe_yaml"])

    # Output on File A
    result_a = TransformationEngine.apply_rules(raw_rows_a, recipe_dict["rules"])

    # Equivalent File B
    raw_rows_b = [
        ["TITULO INFORME", ""],
        ["Fecha", "Importe"],
        ["03/05/2026", "550,25"],
        ["04/05/2026", "990,00"]
    ]
    result_b = TransformationEngine.apply_rules(raw_rows_b, recipe_dict["rules"])

    # Verify deterministic column headers and formatting
    assert result_a["headers"] == ["Fecha", "Importe"]
    assert result_b["headers"] == ["Fecha", "Importe"]
    assert result_a["rows"][0][1] == "1250.50"
    assert result_b["rows"][0][1] == "550.25"
    assert result_a["rows"][0][0] == "2026-05-01"
    assert result_b["rows"][0][0] == "2026-05-03"

def test_recipe_compatibility_check():
    recipe_cols = ["Fecha", "Cliente", "Importe", "IVA"]
    compat_cols = ["Fecha", "Cliente", "Importe", "IVA"]
    warn_cols = ["Fecha", "Cliente", "Importe"]
    incompat_cols = ["Producto", "Stock", "Almacen"]

    res_exact = check_recipe_compatibility("fp1", "fp1", recipe_cols, compat_cols)
    assert res_exact["status"] == "compatible"

    res_warn = check_recipe_compatibility("fp1", "fp2", recipe_cols, warn_cols)
    assert res_warn["status"] in ["compatible", "compatible_with_warnings"]

    res_bad = check_recipe_compatibility("fp1", "fp3", recipe_cols, incompat_cols)
    assert res_bad["status"] == "incompatible"
