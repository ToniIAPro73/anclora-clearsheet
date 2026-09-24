import os
import io
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import yaml

from models import get_db, User, Recipe, Execution, ExternalStorageConnection
from auth import get_current_user_required
from crypto_service import encrypt_dict, decrypt_dict
from connectors import get_connector
from connectors.s3_connector import S3CompatibleConnector
from schema_validator import SchemaCompatibilityService
from engine import NormalizationPlanner
from recipe_service import RecipeExecutionService
from ssrf_validator import SSRFProtectionError

logger = logging.getLogger("cleansheet.connectors")
router = APIRouter(prefix="/connectors", tags=["connectors"])

# ----------------- Request / Response Models -----------------

class S3ConfigModel(BaseModel):
    bucket_name: str
    access_key_id: str
    secret_access_key: str
    region_name: Optional[str] = "us-east-1"
    endpoint_url: Optional[str] = None

class CreateConnectionRequest(BaseModel):
    name: str
    provider_type: str = "s3_compatible"
    s3_config: S3ConfigModel

class UpdateConnectionRequest(BaseModel):
    name: Optional[str] = None
    s3_config: Optional[S3ConfigModel] = None

class TestConnectionRequest(BaseModel):
    provider_type: str = "s3_compatible"
    s3_config: S3ConfigModel

class ExecuteCloudPipelineRequest(BaseModel):
    source_connection_id: str
    source_key: str
    recipe_id: str
    target_connection_id: Optional[str] = None # Defaults to source_connection_id if not provided
    target_key: Optional[str] = None # Defaults to normalized path if not provided
    output_format: Optional[str] = "csv" # csv | xlsx

# ----------------- Connections Management Endpoints -----------------

@router.post("/test")
def test_unsaved_connection(
    req: TestConnectionRequest,
    user: User = Depends(get_current_user_required)
):
    """
    Tests connection against remote storage BEFORE saving it to DB.
    Validates credentials and SSRF endpoint safety.
    """
    try:
        connector = get_connector(req.provider_type, req.s3_config.model_dump())
        res = connector.test_connection()
        return res
    except SSRFProtectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"success": False, "message": f"Error de conexión: {str(e)}"}

@router.post("")
def create_connection(
    req: CreateConnectionRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Creates and saves a user-owned External Storage Connection.
    Credentials are encrypted at-rest using AES-256-GCM.
    """
    # 1. Test connection first
    try:
        connector = get_connector(req.provider_type, req.s3_config.model_dump())
        test_res = connector.test_connection()
    except SSRFProtectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        test_res = {"success": False, "message": str(e)}

    # 2. Build safe unencrypted preview (NO secrets or access keys)
    s3_dict = req.s3_config.model_dump()
    key_preview = f"{s3_dict['access_key_id'][:4]}...{s3_dict['access_key_id'][-4:]}" if len(s3_dict['access_key_id']) > 8 else "sec_***"
    config_preview = {
        "bucket_name": s3_dict["bucket_name"],
        "region_name": s3_dict.get("region_name", "us-east-1"),
        "endpoint_url": s3_dict.get("endpoint_url"),
        "access_key_preview": key_preview
    }

    # 3. Encrypt raw credentials with AES-256-GCM
    encrypted_payload = encrypt_dict(s3_dict)

    conn = ExternalStorageConnection(
        user_id=user.id,
        name=req.name.strip(),
        provider_type=req.provider_type,
        encrypted_config=encrypted_payload,
        config_preview=config_preview,
        last_tested_at=datetime.now(timezone.utc),
        last_test_status="success" if test_res.get("success") else "failed",
        last_test_error=test_res.get("message") if not test_res.get("success") else None
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    return {
        "id": conn.id,
        "name": conn.name,
        "provider_type": conn.provider_type,
        "config_preview": conn.config_preview,
        "last_tested_at": conn.last_tested_at.isoformat() if conn.last_tested_at else None,
        "last_test_status": conn.last_test_status,
        "last_test_error": conn.last_test_error,
        "created_at": conn.created_at.isoformat() if conn.created_at else None
    }

@router.get("")
def list_connections(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Lists external connections strictly owned by the current user.
    Never exposes raw access keys or secret keys.
    """
    conns = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.user_id == user.id
    ).order_by(ExternalStorageConnection.created_at.desc()).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "provider_type": c.provider_type,
            "config_preview": c.config_preview,
            "last_tested_at": c.last_tested_at.isoformat() if c.last_tested_at else None,
            "last_test_status": c.last_test_status,
            "last_test_error": c.last_test_error,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in conns
    ]

@router.delete("/{connection_id}")
def delete_connection(
    connection_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Conexión no encontrada o no autorizada.")

    db.delete(conn)
    db.commit()
    return {"message": "Conexión eliminada correctamente."}

@router.post("/{connection_id}/test")
def test_saved_connection(
    connection_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Conexión no encontrada o no autorizada.")

    decrypted_config = decrypt_dict(conn.encrypted_config)
    try:
        connector = get_connector(conn.provider_type, decrypted_config)
        test_res = connector.test_connection()
        conn.last_tested_at = datetime.now(timezone.utc)
        conn.last_test_status = "success" if test_res.get("success") else "failed"
        conn.last_test_error = test_res.get("message") if not test_res.get("success") else None
        db.commit()
        return test_res
    except Exception as e:
        conn.last_tested_at = datetime.now(timezone.utc)
        conn.last_test_status = "failed"
        conn.last_test_error = str(e)
        db.commit()
        return {"success": False, "message": str(e)}

@router.get("/{connection_id}/objects")
def list_connection_objects(
    connection_id: str,
    prefix: str = "",
    cursor: Optional[str] = None,
    max_keys: int = 50,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Lists objects in the authorized external bucket with pagination."""
    conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Conexión no encontrada o no autorizada.")

    decrypted_config = decrypt_dict(conn.encrypted_config)
    try:
        connector = get_connector(conn.provider_type, decrypted_config)
        result = connector.list_objects(prefix=prefix, cursor=cursor, max_keys=max_keys)
        return {
            "objects": [
                {
                    "key": obj.key,
                    "size_bytes": obj.size_bytes,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag
                }
                for obj in result.objects
            ],
            "next_cursor": result.next_cursor,
            "is_truncated": result.is_truncated,
            "prefix": result.prefix
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al listar objetos remotos: {str(e)}")

# ----------------- Execution Pipeline: Cloud Source -> Recipe -> Cloud Target -----------------

@router.post("/execute-pipeline")
def execute_cloud_pipeline(
    req: ExecuteCloudPipelineRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Cloud Source -> Deterministic Recipe Execution -> Cloud Target
    Guarantees:
    - Same RecipeExecutionService & SchemaCompatibilityService.
    - Full schema drift and column alias resolution.
    - Unified Execution record stored in PostgreSQL.
    - Zero leaks of S3 credentials or raw row values.
    """
    pipeline_start = time.time()

    # 1. Authorize Source Connection
    source_conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == req.source_connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not source_conn:
        raise HTTPException(status_code=404, detail="Conexión de origen no encontrada o no autorizada.")

    # 2. Authorize Target Connection
    target_conn_id = req.target_connection_id or req.source_connection_id
    target_conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == target_conn_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not target_conn:
        raise HTTPException(status_code=404, detail="Conexión de destino no encontrada o no autorizada.")

    # 3. Authorize Recipe
    recipe = db.query(Recipe).filter(
        Recipe.id == req.recipe_id,
        Recipe.user_id == user.id
    ).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no autorizada.")

    recipe_dict = yaml.safe_load(recipe.definition_yaml)
    rules = recipe_dict.get("rules", {})

    # 4. Instantiate Connectors
    src_config = decrypt_dict(source_conn.encrypted_config)
    tgt_config = decrypt_dict(target_conn.encrypted_config)
    src_connector = get_connector(source_conn.provider_type, src_config)
    tgt_connector = get_connector(target_conn.provider_type, tgt_config)

    # 5. Retrieve object metadata and stream source content
    try:
        obj_meta = src_connector.get_object_metadata(req.source_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"El objeto de origen '{req.source_key}' no existe en el almacenamiento remoto.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo metadata de origen: {str(e)}")

    # Stream into temp buffer for normalization
    temp_dir = Path("/tmp/cleansheet_cloud_pipeline")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_src_file = temp_dir / f"src_{uuid.uuid4().hex}_{Path(req.source_key).name}"

    try:
        with open(temp_src_file, "wb") as f_out:
            for chunk in src_connector.read_stream(req.source_key):
                f_out.write(chunk)

        ext = Path(req.source_key).suffix.lower()
        with open(temp_src_file, "rb") as f_in:
            file_bytes = f_in.read()

        raw_rows = RecipeExecutionService.parse_raw_content(file_bytes, ext)
        if not raw_rows:
            raise HTTPException(status_code=400, detail="El archivo remoto está vacío o no contiene filas legibles.")

        # 6. Schema Compatibility and Drift Evaluation
        analysis = NormalizationPlanner.plan(raw_rows)
        drift_res = SchemaCompatibilityService.evaluate(recipe_dict, analysis)

        if drift_res["is_blocking"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Ejecución detenida: se detectó un structural drift bloqueante.",
                    "drift_items": drift_res["drift_items"],
                    "missing_columns": drift_res["missing_columns"]
                }
            )

        # Merge applied aliases into execution rules
        execution_rules = dict(rules)
        if drift_res.get("applied_aliases"):
            execution_rules["column_aliases"] = recipe_dict.get("column_aliases", {})

        # 7. Execute deterministic recipe
        out_format = req.output_format or "csv"
        exec_result = RecipeExecutionService.execute(
            raw_rows=raw_rows,
            rules=execution_rules,
            output_format=out_format,
            original_filename=Path(req.source_key).name,
            user_id=user.id,
            recipe_id=recipe.id,
            context_tag="cloud_pipeline"
        )

        # 8. Write to Cloud Target
        target_path = req.target_key
        if not target_path or not target_path.strip():
            src_stem = Path(req.source_key).stem
            target_path = f"normalized/{src_stem}_clean.{out_format}"

        target_buf = io.BytesIO(exec_result["file_bytes"])
        tgt_write_meta = tgt_connector.write_stream(
            key=target_path,
            stream=target_buf,
            content_type=exec_result["media_type"]
        )

        duration_total_ms = int((time.time() - pipeline_start) * 1000)

        # 9. Update unified Execution in DB
        op_meta = {
            "pipeline_type": "cloud_s3_to_s3",
            "source_connection_id": source_conn.id,
            "source_connection_name": source_conn.name,
            "source_key": req.source_key,
            "source_size_bytes": obj_meta.size_bytes,
            "target_connection_id": target_conn.id,
            "target_connection_name": target_conn.name,
            "target_key": target_path,
            "schema_compatibility": drift_res["status"],
            "drift_detected": [item["message_es"] for item in drift_res.get("drift_items", [])],
            "applied_aliases": drift_res.get("applied_aliases", {})
        }

        if exec_result.get("execution_id"):
            ex_record = db.query(Execution).filter(Execution.id == exec_result["execution_id"]).first()
            if ex_record:
                ex_record.file_name = f"[CLOUD] {Path(req.source_key).name} -> {Path(target_path).name}"
                ex_record.result_metadata = op_meta
                ex_record.duration_ms = duration_total_ms
        db.commit()

        return {
            "execution_id": exec_result.get("execution_id"),
            "status": "completed",
            "source": {
                "connection": source_conn.name,
                "key": req.source_key,
                "size_bytes": obj_meta.size_bytes
            },
            "target": {
                "connection": target_conn.name,
                "key": target_path,
                "bucket": tgt_write_meta.get("bucket"),
                "etag": tgt_write_meta.get("etag")
            },
            "rows_in": exec_result["rows_in"],
            "rows_out": exec_result["rows_out"],
            "changes_count": exec_result["changes_count"],
            "drift_status": drift_res["status"],
            "applied_aliases": drift_res.get("applied_aliases", {}),
            "duration_ms": duration_total_ms
        }
    finally:
        temp_src_file.unlink(missing_ok=True)
