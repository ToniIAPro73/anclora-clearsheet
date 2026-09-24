import io
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import openpyxl
import pandas as pd
import yaml

from models import get_db, SourceFile, Recipe, User
from auth import get_current_user_required
from storage import storage
from heuristics import generate_structure_fingerprint
from engine import NormalizationPlanner, TransformationEngine
from recipe_service import RecipeExecutionService
from csv_detector import CsvDialectDetector

router = APIRouter(prefix="/files", tags=["files"])

# Temporary cache to store uploaded file rows for fast interactive preview recalculation
FILE_CACHE: Dict[str, Dict[str, Any]] = {}

class ApplyRulesRequest(BaseModel):
    file_id: str
    rules: Dict[str, Any]

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """
    Step 1: Upload CSV or Excel file. Requires active authenticated user.
    Saves file in private storage and extracts sheet names.
    """
    filename = file.filename or "upload.csv"
    ext = Path(filename).suffix.lower()
    if ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Formato no compatible. Sube un archivo .csv o .xlsx")

    # Read binary
    content = await file.read()
    file_size = len(content)

    # Save to storage
    storage_key = storage.save_file(io.BytesIO(content), ext)
    file_path = storage.get_file_path(storage_key)

    # Inspect sheets if Excel
    sheets = ["Sheet1"]
    if ext in [".xlsx", ".xls"]:
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheets = wb.sheetnames
            wb.close()
        except Exception:
            sheets = ["Hoja1"]

    # Register in DB (source_file)
    source_file = SourceFile(
        user_id=user.id,
        original_name=filename,
        file_type=ext.replace(".", ""),
        file_size=file_size,
        storage_path=storage_key,
        metadata_json={"sheets": sheets}
    )
    db.add(source_file)
    db.commit()
    db.refresh(source_file)

    return {
        "file_id": source_file.id,
        "filename": filename,
        "file_type": ext.replace(".", ""),
        "file_size": file_size,
        "sheets": sheets,
        "default_sheet": sheets[0] if sheets else "Sheet1"
    }

@router.get("/{file_id}/analyze")
def analyze_file(
    file_id: str,
    sheet: Optional[str] = None,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Step 2: Parse sheet and run deterministic Heuristic Analysis.
    Enforces strict user ownership of file_id.
    """
    source_file = db.query(SourceFile).filter(SourceFile.id == file_id, SourceFile.user_id == user.id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o no autorizado.")

    file_path = storage.get_file_path(source_file.storage_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo temporal expirado.")

    ext = source_file.file_type.lower()
    selected_sheet = sheet or (source_file.metadata_json.get("sheets", ["Sheet1"])[0] if source_file.metadata_json else "Sheet1")

    # Parse raw rows using unified service
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    raw_rows = RecipeExecutionService.parse_raw_content(file_bytes, f".{ext}", sheet_name=selected_sheet)

    if not raw_rows:
        raise HTTPException(status_code=400, detail="El archivo se encuentra vacío.")

    # Cache for preview responsiveness with strict user isolation
    FILE_CACHE[file_id] = {
        "raw_rows": raw_rows,
        "sheet": selected_sheet,
        "user_id": user.id,
        "timestamp": time.time()
    }

    # Execute Heuristic Normalization Planning
    analysis_result = NormalizationPlanner.plan(raw_rows, sheet_name=selected_sheet)

    # Generate initial preview with default rules
    preview_data = TransformationEngine.apply_rules(raw_rows[:150], analysis_result["default_rules"])

    # Update source_file fingerprint in DB
    source_file.structure_fingerprint = analysis_result["structure_fingerprint"]
    db.commit()

    return {
        "file_id": file_id,
        "filename": source_file.original_name,
        "analysis": analysis_result,
        "original_preview": {
            "rows": raw_rows[:100],
            "total_rows": len(raw_rows)
        },
        "normalized_preview": preview_data,
        "python_script": TransformationEngine.generate_python_script(yaml.safe_load(analysis_result["recipe_yaml"]))
    }

@router.post("/preview")
def preview_rules(
    req: ApplyRulesRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Step 3: Interactive real-time recalculation of preview when user tweaks rules in UI.
    Enforces user isolation in cache and database.
    """
    cached = FILE_CACHE.get(req.file_id)
    if not cached or cached.get("user_id") != user.id:
        source_file = db.query(SourceFile).filter(SourceFile.id == req.file_id, SourceFile.user_id == user.id).first()
        if not source_file:
            raise HTTPException(status_code=404, detail="Sesión de archivo no encontrada o no autorizada.")
        file_path = storage.get_file_path(source_file.storage_path)
        ext = source_file.file_type.lower()
        if ext in ["xlsx", "xls"]:
            df = pd.read_excel(file_path, header=None)
        else:
            df_raw = pd.read_csv(file_path, header=None, sep=None, engine="python")
        raw_rows = df_raw.fillna("").values.tolist()
        cached = {"raw_rows": raw_rows, "sheet": "Sheet1", "user_id": user.id, "timestamp": time.time()}
        FILE_CACHE[req.file_id] = cached

    raw_rows = cached["raw_rows"]

    # Transform sample for fast UI responsiveness (first 100 rows)
    transformed_preview = TransformationEngine.apply_rules(raw_rows[:100], req.rules)

    # Build updated Recipe YAML and Python Script
    recipe_dict = {
        "recipe_version": "1.0",
        "structure_fingerprint": generate_structure_fingerprint(transformed_preview["headers"], {}, req.rules.get("remove_top_rows", 0)),
        "source": {"sheet": cached.get("sheet", "Sheet1")},
        "rules": req.rules
    }
    updated_yaml = yaml.dump(recipe_dict, sort_keys=False, allow_unicode=True)
    updated_python = TransformationEngine.generate_python_script(recipe_dict)

    return {
        "preview": transformed_preview,
        "recipe_yaml": updated_yaml,
        "python_script": updated_python
    }

@router.post("/export")
def export_file(
    req: ApplyRulesRequest,
    format: str = "xlsx", # xlsx | csv
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """
    Step 4: Executes complete transformation on the ENTIRE dataset using unified RecipeExecutionService.
    Enforces user ownership on source file.
    """
    source_file = db.query(SourceFile).filter(SourceFile.id == req.file_id, SourceFile.user_id == user.id).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o no autorizado.")

    file_path = storage.get_file_path(source_file.storage_path)
    with open(file_path, "rb") as f:
        content = f.read()

    ext = f".{source_file.file_type.lower()}"
    raw_rows = RecipeExecutionService.parse_raw_content(content, ext)

    exec_result = RecipeExecutionService.execute(
        raw_rows=raw_rows,
        rules=req.rules,
        output_format=format,
        original_filename=source_file.original_name,
        user_id=user.id,
        context_tag="manual_export"
    )

    return FileResponse(
        storage.get_file_path(exec_result["storage_key"]),
        filename=exec_result["filename"],
        media_type=exec_result["media_type"]
    )

@router.post("/stream-process")
async def stream_process_csv(
    file: UploadFile = File(...),
    recipe_id: Optional[str] = Form(None),
    manual_delimiter: Optional[str] = Form(None),
    output_format: str = Form("csv"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required)
):
    """
    Stream Chunked Parsing for large CSV files (up to 250MB):
    - Streams directly to disk avoiding RAM exhaustion.
    - Processes chunks sequentially via RecipeExecutionService.execute_stream_csv.
    - Requires authenticated user session.
    """
    filename = file.filename or "large_data.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Stream parsing está optimizado para archivos CSV grandes (.csv). Para Excel (.xlsx) utiliza el procesamiento estándar."
        )

    # Save to temp location chunk by chunk to avoid holding full file in memory
    temp_dir = Path("/tmp/cleansheet_stream")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / f"stream_in_{uuid.uuid4().hex}.csv"

    total_bytes = 0
    with open(temp_file_path, "wb") as f_out:
        while True:
            chunk = await file.read(1024 * 1024) # 1MB buffer
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > 300 * 1024 * 1024:
                temp_file_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="El archivo excede el límite máximo de streaming permitido.")
            f_out.write(chunk)

    # Determine recipe with strict ownership check
    recipe_rules = None
    active_recipe = None
    if recipe_id:
        active_recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
        if not active_recipe:
            temp_file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")
        recipe_dict = yaml.safe_load(active_recipe.definition_yaml)
        recipe_rules = recipe_dict.get("rules", {})

    if not recipe_rules:
        # Sample first 200 lines to plan rules
        with open(temp_file_path, "r", encoding="utf-8", errors="replace") as f:
            sample_lines = [f.readline() for _ in range(200)]
        import csv
        reader = csv.reader(io.StringIO("".join(sample_lines)))
        sample_rows = [r for r in reader if any(c.strip() for c in r)]
        plan = NormalizationPlanner.plan(sample_rows)
        recipe_rules = plan["default_rules"]

    try:
        exec_result = RecipeExecutionService.execute_stream_csv(
            csv_file_path=str(temp_file_path),
            rules=recipe_rules,
            output_format=output_format,
            original_filename=filename,
            user_id=user.id,
            recipe_id=active_recipe.id if active_recipe else None,
            context_tag="stream_upload",
            manual_delimiter=manual_delimiter
        )
    finally:
        temp_file_path.unlink(missing_ok=True)

    return FileResponse(
        storage.get_file_path(exec_result["storage_key"]),
        filename=exec_result["filename"],
        media_type="text/csv"
    )

@router.post("/detect-dialect")
async def detect_csv_dialect(
    file: UploadFile = File(...),
    manual_delimiter: Optional[str] = Form(None),
    user: User = Depends(get_current_user_required)
):
    """
    Analyzes CSV bytes to detect delimiter (comma, semicolon, tab, pipe),
    quoting and encoding with confidence score and ambiguity warnings.
    Requires authenticated user session.
    """
    content = await file.read(65536) # Read first 64KB for dialect detection
    return CsvDialectDetector.analyze(content, manual_override_delimiter=manual_delimiter)
