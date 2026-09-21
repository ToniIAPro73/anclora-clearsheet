import hashlib
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import polars as pl
import pandas as pd
import numpy as np

def generate_structure_fingerprint(
    column_names: List[str],
    column_types: Dict[str, str],
    detected_header_row: int = 0
) -> str:
    """
    Computes deterministic SHA-256 structure fingerprint based on:
    - Normalized column names
    - Number of columns
    - Inferred semantic types
    - Header row index
    """
    norm_cols = [c.strip().lower() for c in column_names]
    sorted_types = sorted([f"{k}:{v}" for k, v in column_types.items()])
    data_repr = f"cols={len(norm_cols)}|names={','.join(norm_cols)}|types={','.join(sorted_types)}|header_row={detected_header_row}"
    return hashlib.sha256(data_repr.encode("utf-8")).hexdigest()[:16]

def check_recipe_compatibility(recipe_fingerprint: str, file_fingerprint: str, recipe_columns: List[str], file_columns: List[str]) -> Dict[str, Any]:
    """
    Evaluates compatibility between a saved recipe and a candidate file.
    Returns status: 'compatible', 'compatible_with_warnings', or 'incompatible'
    """
    if recipe_fingerprint == file_fingerprint:
        return {
            "status": "compatible",
            "score": 1.0,
            "message_es": "Compatibilidad estructural exacta (100%)",
            "message_en": "Exact structural compatibility (100%)",
            "matched_columns": recipe_columns,
            "missing_columns": []
        }

    recipe_set = set([c.strip().lower() for c in recipe_columns])
    file_set = set([c.strip().lower() for c in file_columns])

    if not recipe_set:
        return {"status": "compatible_with_warnings", "score": 0.5, "message_es": "Receta sin columnas especificadas", "message_en": "Recipe has no specified columns"}

    intersection = recipe_set.intersection(file_set)
    match_ratio = len(intersection) / len(recipe_set)

    missing = list(recipe_set - file_set)
    extra = list(file_set - recipe_set)

    if match_ratio >= 0.85:
        return {
            "status": "compatible",
            "score": round(match_ratio, 2),
            "message_es": f"Compatible ({int(match_ratio*100)}% de coincidencia de columnas)",
            "message_en": f"Compatible ({int(match_ratio*100)}% column match)",
            "matched_columns": list(intersection),
            "missing_columns": missing
        }
    elif match_ratio >= 0.5:
        return {
            "status": "compatible_with_warnings",
            "score": round(match_ratio, 2),
            "message_es": f"Compatible con advertencias ({len(missing)} columnas ausentes)",
            "message_en": f"Compatible with warnings ({len(missing)} missing columns)",
            "matched_columns": list(intersection),
            "missing_columns": missing
        }
    else:
        return {
            "status": "incompatible",
            "score": round(match_ratio, 2),
            "message_es": f"Estructura no compatible (solo coincide {int(match_ratio*100)}%)",
            "message_en": f"Incompatible structure (only {int(match_ratio*100)}% match)",
            "matched_columns": list(intersection),
            "missing_columns": missing
        }

class HeuristicAnalyzer:
    """
    Deterministic file analyzer that inspects raw spreadsheets or CSV data
    Detects:
    1. Title / Banner rows before the actual data table
    2. Multilevel headers
    3. Multiple independent tables on a single sheet
    4. Decimal and thousands separator formatting (European vs US)
    5. Date formats and ambiguous dates (e.g. 01/02/2026)
    6. Completely empty rows and columns
    7. Duplicate headers
    """

    @staticmethod
    def detect_title_rows(raw_rows: List[List[Any]]) -> Tuple[int, float, str]:
        """
        Analyzes the first 25 rows to identify metadata banners or report titles.
        Returns: (header_row_index, confidence, reason)
        """
        if not raw_rows:
            return 0, 1.0, "Empty table"

        num_check = min(20, len(raw_rows))
        densities = []
        for i in range(num_check):
            row = raw_rows[i]
            non_empty = [c for c in row if c is not None and str(c).strip() != ""]
            densities.append(len(non_empty))

        max_density = max(densities) if densities else 0
        if max_density <= 1:
            return 0, 0.9, "Single column or simple structure"

        # Look for sudden jump from sparse row (title banner 1 or 2 cells) to dense row
        for i in range(num_check - 1):
            curr_d = densities[i]
            next_d = densities[i + 1]

            # If row i is metadata banner (e.g. 1-4 sparse key-values like "Generado el:") followed by blank row and table header
            if i + 2 < num_check and densities[i+1] == 0 and densities[i+2] >= max(3, int(max_density * 0.7)):
                return i + 2, 0.95, f"Detected title/metadata banner followed by blank row prior to header at row {i+2}"

            # If both row i and row i+1 are sparse banner rows and row i+2 is full table
            if i + 2 < num_check:
                if curr_d <= 2 and next_d <= 2 and densities[i+2] >= max(3, int(max_density * 0.7)):
                    return i + 2, 0.94, f"Detected multi-row title banner at rows 0..{i+1}"

            # If current row has low density (< max_density * 0.7) and next row reaches full table density (>= max_density * 0.7)
            if curr_d <= 2 and next_d >= max(3, int(max_density * 0.7)):
                conf = 0.95 if curr_d <= 1 else 0.88
                return i + 1, conf, f"Detected title banner at rows 0..{i} (sparse density {curr_d} vs table density {next_d})"

            # If current row has 1 cell and next has higher density (for 2-column tables)
            if max_density == 2 and curr_d <= 1 and next_d >= 2:
                conf = 0.95
                return i + 1, conf, f"Detected title banner at rows 0..{i} (sparse density {curr_d} vs table density {next_d})"

            # If row 0 is title, row 1 empty, row 2 header
            if i + 2 < num_check:
                if curr_d <= 2 and densities[i+1] == 0 and densities[i+2] >= max(3, int(max_density * 0.7)):
                    return i + 2, 0.94, f"Detected title and blank row prior to table header at row {i+2}"

        # If row 0 itself is high density
        if densities[0] >= int(max_density * 0.7):
            return 0, 0.92, "Table begins at first row (dense column distribution)"

        return 0, 0.70, "Defaulted to row 0"

    @staticmethod
    def detect_multilevel_headers(raw_rows: List[List[Any]], header_idx: int) -> Tuple[bool, int, List[str]]:
        """
        Detects if header spans 2 or more rows (e.g. Sales / Net, Tax).
        Returns: (is_multilevel, num_header_rows, flattened_names)
        """
        if header_idx + 1 >= len(raw_rows):
            return False, 1, []

        row1 = [str(c).strip() if c is not None else "" for c in raw_rows[header_idx]]
        row2 = [str(c).strip() if c is not None else "" for c in raw_rows[header_idx + 1]]

        # Multilevel pattern: row1 has empty cells interspersed with categories, row2 has subheaders
        row1_non_empty = [c for c in row1 if c]
        row2_non_empty = [c for c in row2 if c]

        # If both rows are non-empty and row1 has repeated categories or blanks
        if len(row1_non_empty) >= 2 and len(row2_non_empty) >= len(row1_non_empty):
            # Check if row2 looks like subheaders (not data, e.g. text words like 'neto', 'iva', 'total')
            is_subheaders = all(not re.match(r"^\d+([.,]\d+)?$", c) for c in row2_non_empty if c)
            if is_subheaders and len(row1_non_empty) < len(row2_non_empty):
                # Flatten headers deterministically: e.g. "Ventas_Neto"
                flattened = []
                current_parent = ""
                for col_idx in range(max(len(row1), len(row2))):
                    p = row1[col_idx] if col_idx < len(row1) else ""
                    sub = row2[col_idx] if col_idx < len(row2) else ""
                    if p:
                        current_parent = p
                    if current_parent and sub and current_parent.lower() != sub.lower():
                        combined = f"{current_parent}_{sub}"
                    else:
                        combined = sub or current_parent or f"col_{col_idx+1}"
                    flattened.append(combined)
                return True, 2, flattened

        return False, 1, []

    @staticmethod
    def detect_date_inconsistencies(values: List[str]) -> Dict[str, Any]:
        """
        Analyzes string samples for date formats and detects mixed formats or ambiguity (01/02/2026).
        """
        date_patterns = {
            "YYYY-MM-DD": r"^\d{4}-\d{1,2}-\d{1,2}$",
            "DD/MM/YYYY": r"^\d{1,2}/\d{1,2}/\d{4}$",
            "MM/DD/YYYY": r"^\d{1,2}/\d{1,2}/\d{4}$",
            "DD.MM.YYYY": r"^\d{1,2}\.\d{1,2}\.\d{4}$",
            "YYYY/MM/DD": r"^\d{4}/\d{1,2}/\d{1,2}$"
        }

        counts = {}
        ambiguous_count = 0
        samples_tested = 0

        for v in values:
            v_str = str(v).strip()
            if not v_str or v_str.lower() in ["null", "none", "nan", ""]:
                continue

            samples_tested += 1
            # Check for ambiguity in DD/MM/YYYY vs MM/DD/YYYY (both parts <= 12)
            slash_match = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", v_str)
            if slash_match:
                p1, p2, p3 = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
                if p1 <= 12 and p2 <= 12:
                    ambiguous_count += 1

            for fmt, pat in date_patterns.items():
                if re.match(pat, v_str):
                    counts[fmt] = counts.get(fmt, 0) + 1

        is_date_col = samples_tested > 0 and (sum(counts.values()) / samples_tested) >= 0.6
        dominant_format = max(counts, key=counts.get) if counts else None
        is_mixed = len(counts) > 1

        return {
            "is_date": is_date_col,
            "dominant_format": dominant_format,
            "detected_formats": counts,
            "has_mixed_formats": is_mixed,
            "ambiguous_count": ambiguous_count,
            "is_ambiguous": (ambiguous_count / max(1, samples_tested)) > 0.5 and dominant_format in ["DD/MM/YYYY", "MM/DD/YYYY"],
            "confidence": 0.95 if not is_mixed and ambiguous_count == 0 else (0.75 if is_mixed else 0.60)
        }

    @staticmethod
    def detect_decimal_format(values: List[str]) -> Dict[str, Any]:
        """
        Detects European ('1.234,56') vs US ('1,234.56') decimal patterns.
        """
        comma_decimal = 0   # 1.234,56 or 1234,56
        dot_decimal = 0     # 1,234.56 or 1234.56
        samples_tested = 0

        for v in values:
            v_str = str(v).strip()
            if not v_str:
                continue

            # Skip pure integers or phone/postal codes
            if re.match(r"^\d{4,12}$", v_str):
                continue

            # European: e.g. 1.234,50 or 25,50
            if re.match(r"^-?\d{1,3}(\.\d{3})*,\d+$", v_str) or re.match(r"^-?\d+,\d+$", v_str):
                comma_decimal += 1
                samples_tested += 1
            # US: e.g. 1,234.50 or 25.50
            elif re.match(r"^-?\d{1,3}(,\d{3})*\.\d+$", v_str) or re.match(r"^-?\d+\.\d+$", v_str):
                dot_decimal += 1
                samples_tested += 1

        if comma_decimal > dot_decimal:
            decimal_sep = ","
            thousands_sep = "."
            conf = min(0.98, 0.70 + (comma_decimal / max(1, samples_tested)) * 0.28)
            fmt_name = "es-ES (Coma decimal)"
        elif dot_decimal > comma_decimal:
            decimal_sep = "."
            thousands_sep = ","
            conf = min(0.98, 0.70 + (dot_decimal / max(1, samples_tested)) * 0.28)
            fmt_name = "en-US (Punto decimal)"
        else:
            decimal_sep = "."
            thousands_sep = ","
            conf = 0.50
            fmt_name = "Indeterminado / Estándar"

        return {
            "decimal_separator": decimal_sep,
            "thousands_separator": thousands_sep,
            "format_name": fmt_name,
            "confidence": conf,
            "comma_count": comma_decimal,
            "dot_count": dot_decimal
        }

    @staticmethod
    def detect_multiple_tables(raw_rows: List[List[Any]]) -> List[Dict[str, Any]]:
        """
        Identifies if multiple independent tables exist separated by empty rows or new headers.
        """
        if len(raw_rows) < 10:
            return [{"start_row": 0, "end_row": len(raw_rows) - 1, "name": "Table_01"}]

        tables = []
        table_start = None
        empty_streak = 0

        for i, row in enumerate(raw_rows):
            is_empty = all(c is None or str(c).strip() == "" for c in row)
            if is_empty:
                empty_streak += 1
                if table_start is not None and empty_streak >= 2:
                    tables.append({
                        "start_row": table_start,
                        "end_row": i - empty_streak,
                        "name": f"Table_{len(tables)+1:02d}"
                    })
                    table_start = None
            else:
                empty_streak = 0
                if table_start is None:
                    table_start = i

        if table_start is not None:
            tables.append({
                "start_row": table_start,
                "end_row": len(raw_rows) - 1,
                "name": f"Table_{len(tables)+1:02d}"
            })

        return tables if tables else [{"start_row": 0, "end_row": len(raw_rows) - 1, "name": "Table_01"}]
