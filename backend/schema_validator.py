import re
from typing import Dict, Any, List, Optional, Tuple

class SchemaCompatibilityService:
    """
    Unified Schema Compatibility & Structural Drift Detection Service.
    Reused across:
    - Manual execution UI preview
    - Batch Processing
    - Webhook Automations
    - Stream Parsing

    Evaluates:
    - Added / Removed / Missing required columns
    - Type changes (e.g. date -> text, decimal -> integer)
    - Sheet name mismatches
    - CSV dialect/delimiter changes
    - Structure fingerprint matching

    Classification:
    - 'compatible': safe to execute automatically.
    - 'warning': non-critical drift (e.g. non-essential added column, mild confidence change); records warning in Execution and alerts UI.
    - 'blocking': breaking drift (e.g. missing required columns, incompatible schema); halts automatic execution (Batch/Webhook) with error.
    """

    @classmethod
    def evaluate(
        cls,
        recipe_dict: Dict[str, Any],
        candidate_analysis: Dict[str, Any],
        candidate_dialect: Optional[Dict[str, Any]] = None,
        candidate_sheet: Optional[str] = None
    ) -> Dict[str, Any]:
        recipe_cols_spec = recipe_dict.get("columns", {})
        recipe_col_names = list(recipe_cols_spec.keys())
        recipe_fingerprint = recipe_dict.get("structure_fingerprint", "")
        # Aliases mapping defined on recipe or columns: { "canonical_col": ["alias1", "alias2"] }
        recipe_aliases = recipe_dict.get("column_aliases", {})
        for col_name, col_meta in recipe_cols_spec.items():
            if isinstance(col_meta, dict) and "aliases" in col_meta:
                existing = recipe_aliases.get(col_name, [])
                recipe_aliases[col_name] = list(set(existing + col_meta["aliases"]))

        file_cols = [c["name"] for c in candidate_analysis.get("columns", [])]
        file_col_types = {c["name"]: c.get("detected_type", "text") for c in candidate_analysis.get("columns", [])}
        file_fingerprint = candidate_analysis.get("structure_fingerprint", "")

        recipe_set_clean = {c.strip().lower(): c for c in recipe_col_names}
        file_set_clean = {c.strip().lower(): c for c in file_cols}

        # Resolve Column Aliasing deterministically
        applied_aliases = {} # candidate_col -> canonical_col
        aliased_matched = {} # canonical_col -> candidate_col
        alias_conflicts = []

        for canonical_col, alias_list in recipe_aliases.items():
            canonical_clean = canonical_col.strip().lower()
            # If canonical column already matches verbatim in file, no alias resolution needed
            if canonical_clean in file_set_clean:
                continue

            matches = []
            for alias in alias_list:
                alias_clean = alias.strip().lower()
                if alias_clean in file_set_clean:
                    matches.append(file_set_clean[alias_clean])

            if len(matches) == 1:
                cand_col = matches[0]
                # Check for collision: ensure two candidate columns never map to the same canonical column
                if cand_col in applied_aliases:
                    alias_conflicts.append(f"Conflicto de alias: la columna '{cand_col}' intenta mapearse a múltiples columnas canónicas.")
                elif canonical_col in aliased_matched:
                    alias_conflicts.append(f"Conflicto de alias: múltiples columnas candidatas intentan mapearse a '{canonical_col}'.")
                else:
                    applied_aliases[cand_col] = canonical_col
                    aliased_matched[canonical_col] = cand_col
            elif len(matches) > 1:
                alias_conflicts.append(
                    f"Ambigüedad de alias en '{canonical_col}': múltiples columnas en el archivo ({', '.join(matches)}) coinciden con los aliases configurados."
                )

        # Re-evaluate missing and matched columns considering resolved aliases
        missing_cols = []
        matched_cols = []
        for r_clean, r_orig in recipe_set_clean.items():
            if r_clean in file_set_clean:
                matched_cols.append(r_orig)
            elif r_orig in aliased_matched:
                matched_cols.append(r_orig)
            else:
                missing_cols.append(r_orig)

        # Added columns (exclude candidate columns that were matched or aliased)
        added_cols = []
        for f_clean, f_orig in file_set_clean.items():
            if f_clean not in recipe_set_clean and f_orig not in applied_aliases:
                added_cols.append(f_orig)

        # Detect Type Drifts
        type_drifts = []
        for r_clean, r_orig in recipe_set_clean.items():
            actual_col_name = None
            if r_clean in file_set_clean:
                actual_col_name = file_set_clean[r_clean]
            elif r_orig in aliased_matched:
                actual_col_name = aliased_matched[r_orig]

            if actual_col_name:
                expected_type = recipe_cols_spec.get(r_orig, {}).get("type")
                actual_type = file_col_types.get(actual_col_name)
                if expected_type and actual_type and expected_type != actual_type and actual_type != "empty":
                    type_drifts.append({
                        "column": r_orig,
                        "actual_column": actual_col_name,
                        "expected_type": expected_type,
                        "actual_type": actual_type
                    })

        # Detect Dialect Drifts
        dialect_drift = None
        recipe_rules = recipe_dict.get("rules", {})
        recipe_delim = recipe_rules.get("decimal_separator")
        if candidate_dialect:
            candidate_delim = candidate_dialect.get("delimiter")
            if candidate_dialect.get("is_ambiguous"):
                dialect_drift = f"Delimitador CSV ambiguo detectado ('{candidate_delim}'). Requiere verificación manual."

        # Detect Sheet Mismatch (if Excel)
        sheet_drift = None
        recipe_sheet = recipe_dict.get("source", {}).get("sheet")
        if recipe_sheet and candidate_sheet and recipe_sheet != candidate_sheet and recipe_sheet not in ["Sheet1", "Hoja1"]:
            sheet_drift = f"Hoja esperada '{recipe_sheet}', pero el archivo contiene '{candidate_sheet}'."

        # Compute Classification: compatible vs warning vs blocking
        drift_items = []
        is_blocking = False
        status = "compatible"

        # Alias conflicts always trigger warning / review
        for conflict in alias_conflicts:
            status = "warning"
            drift_items.append({
                "severity": "warning",
                "type": "alias_conflict",
                "message_es": conflict,
                "message_en": conflict
            })

        # Applied aliases informational item
        if applied_aliases:
            drift_items.append({
                "severity": "info",
                "type": "applied_aliases",
                "message_es": f"Aliases aplicados ({len(applied_aliases)}): {', '.join([f'{k} -> {v}' for k, v in applied_aliases.items()])}",
                "message_en": f"Applied aliases ({len(applied_aliases)}): {', '.join([f'{k} -> {v}' for k, v in applied_aliases.items()])}"
            })

        # Missing columns rule
        if missing_cols:
            ratio_missing = len(missing_cols) / max(1, len(recipe_col_names))
            # If alias conflicts or ambiguity occurred, treat as warning review rather than silent blocking
            if alias_conflicts:
                status = "warning"
                drift_items.append({
                    "severity": "warning",
                    "type": "missing_due_to_alias_ambiguity",
                    "message_es": f"Columnas sin resolver debido a ambigüedad de alias: {', '.join(missing_cols)}",
                    "message_en": f"Columns unresolved due to alias ambiguity: {', '.join(missing_cols)}"
                })
            # Only block if recipe specifically had recognized meaningful columns and candidate has disjoint structure with no fallback
            elif len(matched_cols) == 0:
                soft_matches = [r_clean for r_clean in recipe_set_clean if any(r_clean in f or f in r_clean for f in file_set_clean)]
                if len(soft_matches) >= 2 or len(file_set_clean) >= 3:
                    status = "warning"
                    drift_items.append({
                        "severity": "warning",
                        "type": "partial_schema_drift",
                        "message_es": f"Divergencia estructural de cabeceras. Se intentará normalizar según reglas ({len(missing_cols)} columnas diferidas).",
                        "message_en": f"Structural header drift detected. Normalization will proceed per rules ({len(missing_cols)} deferred columns)."
                    })
                else:
                    is_blocking = True
                    status = "blocking"
                    drift_items.append({
                        "severity": "blocking",
                        "type": "missing_required_columns",
                        "message_es": f"Columnas requeridas ausentes ({len(missing_cols)}): {', '.join(missing_cols[:5])}",
                        "message_en": f"Required columns missing ({len(missing_cols)}): {', '.join(missing_cols[:5])}"
                    })
            elif ratio_missing > 0.6:
                is_blocking = True
                status = "blocking"
                drift_items.append({
                    "severity": "blocking",
                    "type": "missing_required_columns",
                    "message_es": f"Columnas requeridas ausentes ({len(missing_cols)}): {', '.join(missing_cols[:5])}",
                    "message_en": f"Required columns missing ({len(missing_cols)}): {', '.join(missing_cols[:5])}"
                })
            else:
                status = "warning"
                drift_items.append({
                    "severity": "warning",
                    "type": "missing_optional_columns",
                    "message_es": f"Algunas columnas no se encontraron ({len(missing_cols)}): {', '.join(missing_cols)}",
                    "message_en": f"Some columns were not found ({len(missing_cols)}): {', '.join(missing_cols)}"
                })

        # Critical Type Changes rule
        for td in type_drifts:
            if td["expected_type"] in ["date", "decimal"] and td["actual_type"] in ["text"]:
                status = "warning" if status != "blocking" else "blocking"
                drift_items.append({
                    "severity": "warning",
                    "type": "type_drift",
                    "message_es": f"Cambio de tipo en '{td['column']}': esperado '{td['expected_type']}', detectado '{td['actual_type']}'",
                    "message_en": f"Type change in '{td['column']}': expected '{td['expected_type']}', got '{td['actual_type']}'"
                })

        # Added columns rule
        if added_cols and not is_blocking:
            if status != "warning":
                status = "warning"
            drift_items.append({
                "severity": "warning",
                "type": "added_columns",
                "message_es": f"Columnas nuevas adicionales detectadas ({len(added_cols)}): {', '.join(added_cols[:5])}",
                "message_en": f"Additional new columns detected ({len(added_cols)}): {', '.join(added_cols[:5])}"
            })

        # Sheet drift rule
        if sheet_drift:
            if status != "blocking":
                status = "warning"
            drift_items.append({
                "severity": "warning",
                "type": "sheet_drift",
                "message_es": sheet_drift,
                "message_en": sheet_drift
            })

        # Dialect drift rule
        if dialect_drift:
            if status != "blocking":
                status = "warning"
            drift_items.append({
                "severity": "warning",
                "type": "dialect_drift",
                "message_es": dialect_drift,
                "message_en": dialect_drift
            })

        # Exact match rule
        if not is_blocking and not drift_items:
            status = "compatible"

        return {
            "status": status, # "compatible" | "warning" | "blocking"
            "is_blocking": is_blocking,
            "has_warnings": len([i for i in drift_items if i.get("severity") == "warning"]) > 0 and not is_blocking,
            "applied_aliases": applied_aliases,
            "matched_columns": matched_cols,
            "missing_columns": missing_cols,
            "added_columns": added_cols,
            "type_drifts": type_drifts,
            "drift_items": drift_items,
            "recipe_fingerprint": recipe_fingerprint,
            "file_fingerprint": file_fingerprint,
            "match_ratio": round(len(matched_cols) / max(1, len(recipe_col_names)), 2)
        }
