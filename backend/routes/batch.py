import io
import os
import time
import uuid
import json
import zipfile
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import yaml

from models import get_db, Recipe, Execution, User
from auth import get_current_user_optional, get_current_user_required
from storage import storage
from schema_validator import SchemaCompatibilityService
from engine import NormalizationPlanner
from recipe_service import RecipeExecutionService, validate_file_content

logger = logging.getLogger("cleansheet.api")
router = APIRouter(prefix="/batch", tags=["batch"])

@router.post("/process")
async def batch_process(
    files: List[UploadFile] = File(...),
    recipe_id: Optional[str] = Form(None),
    output_format: str = Form("xlsx"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Hardened Batch Processing with partial success tolerance:
    - Failed or corrupted files do NOT fail the batch.
    - ZIP contains only successfully normalized files + a manifest.json and manifest.csv.
    - Enforces ownership authorization if recipe_id is provided by an authenticated user.
    - Enforces magic bytes/size validation per file.
    - Uses unified RecipeExecutionService for identical transformation logic.
    """
    batch_start_time = time.time()

    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos para procesar por lotes.")

    # Recipe authorization check
    active_recipe = None
    recipe_rules = None
    if recipe_id:
        active_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not active_recipe:
            raise HTTPException(status_code=404, detail="La receta especificada no existe.")
        if active_recipe.user_id and (not user or active_recipe.user_id != user.id):
            raise HTTPException(status_code=403, detail="No tienes autorización para usar esta receta privada.")
        recipe_dict = yaml.safe_load(active_recipe.definition_yaml)
        recipe_rules = recipe_dict.get("rules", {})

    processed_items = []
    manifest_records = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            file_start = time.time()
            filename = file.filename or "archivo"
            try:
                content = await file.read()
                # 1. Validation (size, extension, magic bytes)
                is_valid, ext, err_msg = validate_file_content(content, filename)
                if not is_valid:
                    duration_ms = int((time.time() - file_start) * 1000)
                    manifest_records.append({
                        "original_name": filename,
                        "execution_id": None,
                        "status": "failed",
                        "duration_ms": duration_ms,
                        "rows_in": 0,
                        "rows_out": 0,
                        "error": err_msg
                    })
                    continue

                # 2. Parse raw rows using unified service
                raw_rows = RecipeExecutionService.parse_raw_content(content, ext)
                if not raw_rows:
                    manifest_records.append({
                        "original_name": filename,
                        "execution_id": None,
                        "status": "failed",
                        "duration_ms": int((time.time() - file_start) * 1000),
                        "rows_in": 0,
                        "rows_out": 0,
                        "error": "El archivo está vacío o no contiene filas legibles."
                    })
                    continue

                # 3. Determine rules & evaluate drift if recipe provided
                current_rules = recipe_rules
                drift_warnings = []
                if not current_rules:
                    analysis = NormalizationPlanner.plan(raw_rows)
                    current_rules = analysis["default_rules"]
                else:
                    analysis = NormalizationPlanner.plan(raw_rows)
                    drift_eval = SchemaCompatibilityService.evaluate(recipe_dict, analysis)
                    if drift_eval["is_blocking"]:
                        duration_ms = int((time.time() - file_start) * 1000)
                        manifest_records.append({
                            "original_name": filename,
                            "execution_id": None,
                            "status": "failed",
                            "duration_ms": duration_ms,
                            "rows_in": len(raw_rows),
                            "rows_out": 0,
                            "error": f"Drift estructural bloqueante: faltan columnas requeridas {drift_eval['missing_columns']}"
                        })
                        continue
                    elif drift_eval.get("drift_items"):
                        drift_warnings = [d["message_es"] for d in drift_eval["drift_items"]]

                # Apply aliases if resolved
                execution_rules = dict(current_rules)
                if active_recipe and drift_eval.get("applied_aliases"):
                    execution_rules["column_aliases"] = recipe_dict.get("column_aliases", {})

                # 4. Execute transformation via unified RecipeExecutionService
                exec_result = RecipeExecutionService.execute(
                    raw_rows=raw_rows,
                    rules=execution_rules,
                    output_format=output_format,
                    original_filename=filename,
                    user_id=user.id if user else None,
                    recipe_id=active_recipe.id if active_recipe else None,
                    context_tag="batch"
                )

                # Add to ZIP
                zip_file.writestr(exec_result["filename"], exec_result["file_bytes"])

                processed_items.append({
                    "original_name": filename,
                    "clean_name": exec_result["filename"],
                    "rows_in": exec_result["rows_in"],
                    "rows_out": exec_result["rows_out"],
                    "changes_count": exec_result["changes_count"],
                    "storage_key": exec_result["storage_key"],
                    "warnings": drift_warnings,
                    "status": "completed"
                })

                manifest_records.append({
                    "original_name": filename,
                    "clean_name": exec_result["filename"],
                    "execution_id": exec_result["execution_id"],
                    "status": "completed",
                    "duration_ms": exec_result["duration_ms"],
                    "rows_in": exec_result["rows_in"],
                    "rows_out": exec_result["rows_out"],
                    "transformations_count": exec_result["changes_count"],
                    "warnings": "; ".join(drift_warnings) if drift_warnings else None,
                    "error": None
                })
            except Exception as e:
                manifest_records.append({
                    "original_name": filename,
                    "execution_id": None,
                    "status": "failed",
                    "duration_ms": int((time.time() - file_start) * 1000),
                    "rows_in": 0,
                    "rows_out": 0,
                    "error": str(e)
                })

        # Append manifest.json and manifest.csv to the ZIP
        manifest_json_str = json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_submitted": len(files),
            "successful_count": len(processed_items),
            "failed_count": len(manifest_records) - len(processed_items),
            "records": manifest_records
        }, indent=2)
        zip_file.writestr("manifest.json", manifest_json_str.encode("utf-8"))

        manifest_df = pd.DataFrame(manifest_records)
        manifest_csv_buf = io.BytesIO()
        manifest_df.to_csv(manifest_csv_buf, index=False)
        zip_file.writestr("manifest.csv", manifest_csv_buf.getvalue())

    zip_buffer.seek(0)
    zip_key = storage.save_file(zip_buffer, "zip")

    # Record batch execution in DB if user is authenticated
    batch_exec_id = None
    if user:
        try:
            total_rows_in = sum(p["rows_in"] for p in processed_items)
            total_rows_out = sum(p["rows_out"] for p in processed_items)
            batch_exec = Execution(
                user_id=user.id,
                recipe_id=active_recipe.id if active_recipe else None,
                source_file_id=None,
                file_name=f"[BATCH_{len(files)}_FILES] {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                rows_input=total_rows_in,
                rows_output=total_rows_out,
                columns_input=0,
                columns_output=0,
                transformations_count=sum(r.get("transformations_count", 0) for r in manifest_records if r.get("transformations_count")),
                duration_ms=int((time.time() - batch_start_time) * 1000),
                result_storage_path=zip_key,
                result_metadata={
                    "batch_id": f"batch_{uuid.uuid4().hex[:12]}",
                    "total_files": len(files),
                    "successful_count": len(processed_items),
                    "failed_count": len(manifest_records) - len(processed_items),
                    "recipe_name": active_recipe.name if active_recipe else "Auto-planificado",
                    "manifest": manifest_records
                },
                status="completed" if len(processed_items) == len(files) else ("partial_success" if len(processed_items) > 0 else "failed")
            )
            db.add(batch_exec)
            db.commit()
            db.refresh(batch_exec)
            batch_exec_id = batch_exec.id
        except Exception as e:
            logger.warning(f"Could not record batch execution: {e}")

    return {
        "batch_id": batch_exec_id,
        "total_files": len(files),
        "successful_files": len(processed_items),
        "failed_files": len(manifest_records) - len(processed_items),
        "results": processed_items,
        "manifest": manifest_records,
        "zip_storage_key": zip_key,
        "zip_download_url": f"/api/batch/download/{zip_key}"
    }

@router.get("/download/{storage_key}")
def download_batch_zip(storage_key: str):
    file_path = storage.get_file_path(storage_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo comprimido no encontrado o expirado.")
    return FileResponse(
        file_path,
        filename="cleansheet_lote_normalizado.zip",
        media_type="application/zip"
    )

@router.get("/executions")
def list_batch_executions(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Phase 2: Lists past Batch executions for the authenticated user.
    """
    executions = db.query(Execution).filter(
        Execution.user_id == user.id,
        Execution.file_name.like("%[BATCH_%")
    ).order_by(Execution.created_at.desc()).limit(30).all()

    results = []
    for ex in executions:
        meta = ex.result_metadata or {}
        recipe = db.query(Recipe).filter(Recipe.id == ex.recipe_id).first() if ex.recipe_id else None
        results.append({
            "batch_id": ex.id,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "recipe_name": recipe.name if recipe else meta.get("recipe_name", "Auto-planificado"),
            "recipe_id": ex.recipe_id,
            "total_files": meta.get("total_files", 0),
            "successful_count": meta.get("successful_count", 0),
            "failed_count": meta.get("failed_count", 0),
            "rows_in": ex.rows_input,
            "rows_out": ex.rows_output,
            "duration_ms": ex.duration_ms,
            "status": ex.status,
            "manifest": meta.get("manifest", [])
        })
    return results

@router.get("/executions/{execution_id}")
def get_batch_execution_detail(
    execution_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Phase 2: Webhook/Batch Inspector Detail with strict user isolation.
    """
    ex = db.query(Execution).filter(
        Execution.id == execution_id,
        Execution.user_id == user.id
    ).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Ejecución de lote no encontrada o no autorizada.")

    meta = ex.result_metadata or {}
    recipe = db.query(Recipe).filter(Recipe.id == ex.recipe_id).first() if ex.recipe_id else None

    return {
        "batch_id": ex.id,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
        "recipe_name": recipe.name if recipe else meta.get("recipe_name", "Auto-planificado"),
        "recipe_id": ex.recipe_id,
        "total_files": meta.get("total_files", 0),
        "successful_count": meta.get("successful_count", 0),
        "failed_count": meta.get("failed_count", 0),
        "rows_in": ex.rows_input,
        "rows_out": ex.rows_output,
        "duration_ms": ex.duration_ms,
        "status": ex.status,
        "manifest": meta.get("manifest", []),
        "zip_storage_key": ex.result_storage_path
    }
