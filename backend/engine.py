import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import yaml
import polars as pl
import pandas as pd
from heuristics import HeuristicAnalyzer, generate_structure_fingerprint

class NormalizationPlanner:
    """
    Constructs a deterministic normalization proposal based on raw spreadsheet analysis.
    Adheres strictly to the 'Conservative Hybrid Preset':
    - Auto-detects title rows, multilevel headers, dates, decimal separators, empty rows/columns
    - Keeps original column names by default (no automatic snake_case or translation)
    - Proposes ISO YYYY-MM-DD for dates when confident, flags ambiguous dates
    - Generates full structured changes summary and recipe definition
    """

    @classmethod
    def plan(
        cls,
        raw_rows: List[List[Any]],
        sheet_name: str = "Sheet1",
        custom_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        rules = custom_rules or {}

        # 1. Detect title / banner rows
        detected_header_row, title_conf, title_reason = HeuristicAnalyzer.detect_title_rows(raw_rows)
        # Allow user override
        header_row_idx = rules.get("header_row", detected_header_row)

        # 2. Check for multilevel header
        is_multilevel, num_header_rows, flattened_names = HeuristicAnalyzer.detect_multilevel_headers(raw_rows, header_row_idx)
        data_start_row = header_row_idx + (num_header_rows if is_multilevel else 1)

        # Extract column names
        if is_multilevel and flattened_names:
            col_names = flattened_names
        elif header_row_idx < len(raw_rows):
            raw_headers = raw_rows[header_row_idx]
            col_names = [str(c).strip() if c is not None and str(c).strip() != "" else f"col_{idx+1}" for idx, c in enumerate(raw_headers)]
        else:
            col_names = [f"col_{i+1}" for i in range(len(raw_rows[0]) if raw_rows else 0)]

        # Handle duplicate headers deterministically: e.g. importe, importe_2
        seen_headers = {}
        unique_col_names = []
        has_duplicates = False
        for c in col_names:
            c_clean = c.strip()
            if c_clean in seen_headers:
                seen_headers[c_clean] += 1
                unique_col_names.append(f"{c_clean}_{seen_headers[c_clean]}")
                has_duplicates = True
            else:
                seen_headers[c_clean] = 1
                unique_col_names.append(c_clean)
        col_names = unique_col_names

        # 3. Detect multiple tables
        tables = HeuristicAnalyzer.detect_multiple_tables(raw_rows)

        # Extract data rows for sample analysis
        data_rows = raw_rows[data_start_row:]
        total_data_rows = len(data_rows)

        # Analyze column data types & empty columns
        col_analyses = []
        column_types = {}
        empty_col_indices = []

        for c_idx, c_name in enumerate(col_names):
            # Sample up to 200 values from column
            sample_vals = []
            for r in data_rows[:200]:
                if c_idx < len(r):
                    sample_vals.append(r[c_idx])

            non_empty_vals = [str(v).strip() for v in sample_vals if v is not None and str(v).strip() != ""]

            if not non_empty_vals:
                empty_col_indices.append(c_idx)
                col_type = "empty"
                conf = 1.0
                date_info = {}
                dec_info = {}
            else:
                # Run date heuristic
                date_info = HeuristicAnalyzer.detect_date_inconsistencies(non_empty_vals)
                # Run decimal heuristic
                dec_info = HeuristicAnalyzer.detect_decimal_format(non_empty_vals)

                if date_info["is_date"]:
                    col_type = "date"
                    conf = date_info["confidence"]
                elif dec_info["confidence"] > 0.65:
                    col_type = "decimal"
                    conf = dec_info["confidence"]
                else:
                    # Check integer
                    all_int = all(re.match(r"^-?\d+$", v) for v in non_empty_vals)
                    if all_int:
                        col_type = "integer"
                        conf = 0.95
                    else:
                        col_type = "text"
                        conf = 0.90

            column_types[c_name] = col_type
            col_analyses.append({
                "index": c_idx,
                "name": c_name,
                "detected_type": col_type,
                "confidence": conf,
                "date_info": date_info,
                "decimal_info": dec_info,
                "is_empty": c_idx in empty_col_indices
            })

        # Global decimal detection
        all_samples = []
        for r in data_rows[:100]:
            all_samples.extend([str(v).strip() for v in r if v is not None])
        global_dec = HeuristicAnalyzer.detect_decimal_format(all_samples)

        # Build list of detected problems and proposed transformations
        transformations_summary = []
        if header_row_idx > 0:
            transformations_summary.append({
                "type": "remove_title_rows",
                "label_es": f"{header_row_idx} filas de título iniciales detectadas",
                "label_en": f"{header_row_idx} title/banner rows detected",
                "detail_es": f"Las filas 0 a {header_row_idx-1} no pertenecen a la tabla tabular.",
                "detail_en": f"Rows 0 to {header_row_idx-1} do not belong to tabular data.",
                "action": "remove",
                "confidence": title_conf
            })

        if is_multilevel:
            transformations_summary.append({
                "type": "multilevel_header",
                "label_es": f"Cabecera multinivel ({num_header_rows} filas) aplanada",
                "label_en": f"Multilevel header ({num_header_rows} rows) flattened",
                "detail_es": "Se han unificado categorías y sub-encabezados en nombres únicos.",
                "detail_en": "Categories and sub-headers merged into unique column headers.",
                "action": "flatten",
                "confidence": 0.92
            })

        if has_duplicates:
            transformations_summary.append({
                "type": "duplicate_headers",
                "label_es": "Cabeceras duplicadas corregidas",
                "label_en": "Duplicate headers disambiguated",
                "detail_es": "Se añadieron sufijos numéricos deterministas a columnas repetidas.",
                "detail_en": "Deterministic numerical suffixes added to repeated headers.",
                "action": "disambiguate",
                "confidence": 1.0
            })

        date_cols = [c for c in col_analyses if c["detected_type"] == "date"]
        if date_cols:
            transformations_summary.append({
                "type": "date_normalization",
                "label_es": f"{len(date_cols)} columna(s) de fecha detectadas",
                "label_en": f"{len(date_cols)} date column(s) detected",
                "detail_es": "Propuesta de salida normalizada a formato estándar YYYY-MM-DD.",
                "detail_en": "Proposed normalization to standard ISO YYYY-MM-DD.",
                "action": "normalize_date",
                "confidence": min([c["confidence"] for c in date_cols])
            })

        ambiguous_dates = [c for c in date_cols if c.get("date_info", {}).get("is_ambiguous")]
        if ambiguous_dates:
            transformations_summary.append({
                "type": "ambiguous_date_warning",
                "label_es": f"Advertencia: {len(ambiguous_dates)} columna(s) con fechas ambiguas (ej. 01/02/2026)",
                "label_en": f"Warning: {len(ambiguous_dates)} column(s) with ambiguous dates (e.g. 01/02/2026)",
                "detail_es": "Requiere confirmar orden día/mes según región elegida.",
                "detail_en": "Requires verifying day/month order per selected locale.",
                "action": "warn",
                "confidence": 0.60
            })

        decimal_cols = [c for c in col_analyses if c["detected_type"] == "decimal"]
        if decimal_cols:
            transformations_summary.append({
                "type": "decimal_normalization",
                "label_es": f"{len(decimal_cols)} columna(s) numéricas/decimales identificadas",
                "label_en": f"{len(decimal_cols)} decimal/numeric column(s) identified",
                "detail_es": f"Formato detectado: {global_dec['format_name']}.",
                "detail_en": f"Detected format: {global_dec['format_name']}.",
                "action": "normalize_decimal",
                "confidence": global_dec["confidence"]
            })

        if empty_col_indices:
            transformations_summary.append({
                "type": "empty_columns",
                "label_es": f"{len(empty_col_indices)} columna(s) completamente vacías",
                "label_en": f"{len(empty_col_indices)} completely empty column(s)",
                "detail_es": "Se propone su eliminación para mantener un dataset limpio.",
                "detail_en": "Proposed removal to keep dataset clean.",
                "action": "remove",
                "confidence": 1.0
            })

        # Calculate structure fingerprint
        fingerprint = generate_structure_fingerprint(col_names, column_types, header_row_idx)

        # Default Recipe Structure (Conservative Hybrid Preset)
        recipe_dict = {
            "recipe_version": "1.0",
            "name": f"Limpieza {sheet_name}",
            "structure_fingerprint": fingerprint,
            "source": {
                "sheet": sheet_name,
                "detected_header_row": header_row_idx,
                "is_multilevel": is_multilevel
            },
            "rules": {
                "remove_top_rows": header_row_idx,
                "remove_empty_rows": rules.get("remove_empty_rows", True),
                "remove_empty_columns": rules.get("remove_empty_columns", True),
                "normalize_headers_case": rules.get("normalize_headers_case", "preserve"), # preserve | snake_case | lower
                "date_output_format": rules.get("date_output_format", "YYYY-MM-DD"),
                "date_input_preference": rules.get("date_input_preference", "auto"), # auto | DMY | MDY
                "decimal_separator": rules.get("decimal_separator", global_dec["decimal_separator"]),
                "thousands_separator": rules.get("thousands_separator", global_dec["thousands_separator"]),
                "output_decimal_separator": rules.get("output_decimal_separator", ".")
            },
            "columns": {
                c["name"]: {
                    "type": c["detected_type"],
                    "confidence": c["confidence"]
                }
                for c in col_analyses
            }
        }

        recipe_yaml_str = yaml.dump(recipe_dict, sort_keys=False, allow_unicode=True)

        return {
            "sheet_name": sheet_name,
            "structure_fingerprint": fingerprint,
            "total_raw_rows": len(raw_rows),
            "total_data_rows": total_data_rows,
            "header_row_index": header_row_idx,
            "is_multilevel": is_multilevel,
            "columns": col_analyses,
            "detected_tables": tables,
            "global_decimal_detection": global_dec,
            "transformations_summary": transformations_summary,
            "default_rules": recipe_dict["rules"],
            "recipe_yaml": recipe_yaml_str
        }

class TransformationEngine:
    """
    Executes deterministic transformations on tabular data given explicit rules.
    Outputs clean tabular data + cell-by-cell change tracking for Before/After view.
    """

    @classmethod
    def apply_rules(
        cls,
        raw_rows: List[List[Any]],
        rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        header_row = int(rules.get("remove_top_rows", 0))
        if header_row >= len(raw_rows):
            header_row = 0

        # Check multilevel
        is_multilevel, num_header_rows, flattened = HeuristicAnalyzer.detect_multilevel_headers(raw_rows, header_row)
        data_start = header_row + (num_header_rows if is_multilevel else 1)

        # Header extraction
        if is_multilevel and flattened:
            headers = flattened
        elif header_row < len(raw_rows):
            headers = [str(c).strip() if c is not None and str(c).strip() != "" else f"col_{i+1}" for i, c in enumerate(raw_rows[header_row])]
        else:
            headers = [f"col_{i+1}" for i in range(len(raw_rows[0]) if raw_rows else 0)]

        # Apply Column Aliasing if present in rules
        column_aliases = rules.get("column_aliases", {})
        if column_aliases:
            aliased_headers = []
            for h in headers:
                canonical = None
                for c_canon, a_list in column_aliases.items():
                    if h.lower() in [a.lower() for a in a_list]:
                        canonical = c_canon
                        break
                aliased_headers.append(canonical or h)
            headers = aliased_headers

        # Header casing
        case_rule = rules.get("normalize_headers_case", "preserve")
        if case_rule == "snake_case":
            clean_headers = []
            for h in headers:
                s = re.sub(r"[^\w\s-]", "", h).strip()
                s = re.sub(r"[-\s]+", "_", s).lower()
                clean_headers.append(s)
            headers = clean_headers

        data_rows = raw_rows[data_start:]

        # Rule: Remove empty rows
        remove_empty_rows = rules.get("remove_empty_rows", True)
        filtered_rows = []
        for r in data_rows:
            is_empty = all(c is None or str(c).strip() == "" for c in r)
            if not (remove_empty_rows and is_empty):
                filtered_rows.append(r)

        # Rule: Remove empty columns
        remove_empty_cols = rules.get("remove_empty_columns", True)
        col_count = len(headers)
        active_col_indices = []
        for col_i in range(col_count):
            has_val = False
            for r in filtered_rows:
                if col_i < len(r) and r[col_i] is not None and str(r[col_i]).strip() != "":
                    has_val = True
                    break
            if not remove_empty_cols or has_val:
                active_col_indices.append(col_i)

        final_headers = [headers[i] for i in active_col_indices]

        # Normalization configurations
        dec_sep = rules.get("decimal_separator", ",")
        thousand_sep = rules.get("thousands_separator", ".")
        out_dec = rules.get("output_decimal_separator", ".")
        date_out_fmt = rules.get("date_output_format", "YYYY-MM-DD")
        date_pref = rules.get("date_input_preference", "auto")

        normalized_rows = []
        changes_log = [] # List of modified cells for UI diff inspection

        for row_idx, r in enumerate(filtered_rows):
            norm_row = []
            for new_col_idx, orig_col_idx in enumerate(active_col_indices):
                orig_val = r[orig_col_idx] if orig_col_idx < len(r) else ""
                val_str = str(orig_val).strip() if orig_val is not None else ""

                norm_val = val_str
                change_rule = None
                change_reason = None

                if val_str:
                    # Try Decimal normalization
                    # If matches European: 1.234,56 or 1234,56
                    if dec_sep == "," and re.match(r"^-?\d{1,3}(\.\d{3})*,\d+$", val_str):
                        clean_num = val_str.replace(".", "").replace(",", out_dec)
                        norm_val = clean_num
                        change_rule = "decimal_separator"
                        change_reason = "Formato decimal europeo normalizado"
                    elif dec_sep == "," and re.match(r"^-?\d+,\d+$", val_str):
                        clean_num = val_str.replace(",", out_dec)
                        norm_val = clean_num
                        change_rule = "decimal_separator"
                        change_reason = "Coma decimal normalizada a punto"
                    elif dec_sep == "." and thousand_sep == "," and re.match(r"^-?\d{1,3}(,\d{3})*\.\d+$", val_str):
                        clean_num = val_str.replace(",", "")
                        norm_val = clean_num
                        change_rule = "thousands_separator"
                        change_reason = "Separador de miles eliminado"

                    # Try Date normalization
                    date_match = re.match(r"^(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})$", val_str)
                    if date_match and change_rule is None:
                        p1, p2, p3 = date_match.group(1), date_match.group(2), date_match.group(3)
                        # Detect year part
                        if len(p1) == 4: # YYYY-MM-DD or YYYY/MM/DD
                            year, month, day = int(p1), int(p2), int(p3)
                        elif len(p3) == 4 or len(p3) == 2:
                            year = int(p3) if len(p3) == 4 else (2000 + int(p3))
                            if date_pref == "MDY":
                                month, day = int(p1), int(p2)
                            else: # Default DMY (European standard)
                                day, month = int(p1), int(p2)
                        else:
                            year, month, day = None, None, None

                        if year and 1 <= month <= 12 and 1 <= day <= 31:
                            if date_out_fmt == "YYYY-MM-DD":
                                norm_val = f"{year:04d}-{month:02d}-{day:02d}"
                            elif date_out_fmt == "DD/MM/YYYY":
                                norm_val = f"{day:02d}/{month:02d}/{year:04d}"
                            elif date_out_fmt == "MM/DD/YYYY":
                                norm_val = f"{month:02d}/{day:02d}/{year:04d}"

                            if norm_val != val_str:
                                change_rule = "date_normalization"
                                change_reason = f"Fecha normalizada a {date_out_fmt}"

                if norm_val != val_str:
                    changes_log.append({
                        "row": row_idx,
                        "col": new_col_idx,
                        "column_name": final_headers[new_col_idx],
                        "original": val_str,
                        "normalized": norm_val,
                        "rule": change_rule,
                        "reason": change_reason
                    })

                norm_row.append(norm_val)

            normalized_rows.append(norm_row)

        return {
            "headers": final_headers,
            "rows": normalized_rows,
            "total_rows": len(normalized_rows),
            "total_cols": len(final_headers),
            "changes_count": len(changes_log),
            "changes_sample": changes_log[:200]
        }

    @classmethod
    def generate_python_script(cls, recipe_dict: Dict[str, Any]) -> str:
        """
        Generates clean, readable, deterministic Python script using Pandas.
        No eval or dynamic unsafe execution.
        """
        rules = recipe_dict.get("rules", {})
        header_row = rules.get("remove_top_rows", 0)
        dec_sep = rules.get("decimal_separator", ",")
        thousand_sep = rules.get("thousands_separator", ".")
        out_fmt = rules.get("date_output_format", "YYYY-MM-DD")
        sheet = recipe_dict.get("source", {}).get("sheet", "Sheet1")

        script = f'''"""
Anclora CleanSheet - Script Reproducible Determinista
Generado automáticamente según Receta v{recipe_dict.get("recipe_version", "1.0")}
Fingerprint: {recipe_dict.get("structure_fingerprint", "N/A")}
"""

import os
import re
import pandas as pd


def clean_data(input_path: str, output_path: str) -> None:
    """
    Limpia y normaliza el archivo especificado aplicando las reglas exactas
    definidas en la receta de Anclora CleanSheet.
    """
    ext = os.path.splitext(input_path)[1].lower()

    # 1. Carga de datos respetando fila de encabezado
    if ext in [".xlsx", ".xls"]:
        df = pd.read_excel(input_path, sheet_name="{sheet}", skiprows={header_row})
    else:
        df = pd.read_csv(input_path, skiprows={header_row})

    # 2. Eliminación de filas y columnas vacías
    if {rules.get("remove_empty_rows", True)}:
        df = df.dropna(how="all")

    if {rules.get("remove_empty_columns", True)}:
        df = df.dropna(axis=1, how="all")

    # 3. Normalización de cabeceras
    if "{rules.get("normalize_headers_case")}" == "snake_case":
        df.columns = [
            re.sub(r"[-\\s]+", "_", re.sub(r"[^\\w\\s-]", "", str(c)).strip()).lower()
            for c in df.columns
        ]

    # 4. Normalización de formato decimal
    for col in df.select_dtypes(include=["object"]).columns:
        # Detectar patrón decimal europeo (ej. 1.234,56 o 1234,56)
        if df[col].astype(str).str.contains(r"^\\s*-?\\d+(\\.\\d{{3}})*,\\d+\\s*$", regex=True).any():
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 5. Exportación del resultado limpio
    out_ext = os.path.splitext(output_path)[1].lower()
    if out_ext in [".xlsx", ".xls"]:
        df.to_excel(output_path, index=False)
    else:
        df.to_csv(output_path, index=False)

    print(f"Limpieza completada con éxito: {{len(df)}} filas exportadas a {{output_path}}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        clean_data(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python clean_script.py <archivo_origen> <archivo_destino>")
'''
        return script
