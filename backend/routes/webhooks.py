import uuid
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import yaml

from models import get_db, AutomationWebhook, Recipe, Execution, User
from auth import get_current_user_required
from storage import storage
from crypto_service import encrypt_secret, decrypt_secret
from schema_validator import SchemaCompatibilityService
from engine import NormalizationPlanner
from recipe_service import (
    RecipeExecutionService, validate_file_content, verify_hmac_signature,
    check_rate_limit
)

logger = logging.getLogger("cleansheet.api")
router = APIRouter(tags=["webhooks"])

class CreateAutomationRequest(BaseModel):
    name: str
    recipe_id: str
    target_format: Optional[str] = "xlsx"

# ----------------- Webhook Execution Inspector -----------------
@router.get("/automations/{automation_id}/executions")
def get_automation_executions(
    automation_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Phase 2: Webhook Execution Inspector.
    Retrieves operational audit records for a webhook strictly owned by the authenticated user.
    SECURITY: Never exposes raw cell values, secrets, tokens, signed URLs or auth headers!
    """
    webhook = db.query(AutomationWebhook).filter(
        AutomationWebhook.id == automation_id,
        AutomationWebhook.user_id == user.id
    ).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook no encontrado o no autorizado.")

    recipe = db.query(Recipe).filter(Recipe.id == webhook.recipe_id).first() if webhook.recipe_id else None

    # Query latest 50 executions associated with this webhook
    context_prefix = f"webhook_{webhook.name}"
    executions = db.query(Execution).filter(
        Execution.user_id == user.id,
        Execution.recipe_id == webhook.recipe_id
    ).order_by(Execution.created_at.desc()).limit(50).all()

    audit_records = []
    for ex in executions:
        meta = ex.result_metadata or {}
        # Only include executions that originated from webhooks
        if meta.get("webhook_name") == webhook.name or ex.file_name.startswith(f"[{webhook.name}]"):
            audit_records.append({
                "execution_id": ex.id,
                "timestamp": ex.created_at.isoformat() if ex.created_at else None,
                "filename": ex.file_name,
                "file_size_bytes": meta.get("file_size_bytes", 0),
                "rows_input": ex.rows_input,
                "rows_output": ex.rows_output,
                "transformations_count": ex.transformations_count,
                "duration_ms": ex.duration_ms,
                "status": ex.status,
                # Operational security metadata
                "hmac_status": meta.get("hmac_status", "none"),
                "anti_replay_status": meta.get("anti_replay_status", "none"),
                "schema_compatibility": meta.get("schema_compatibility", "unknown"),
                "drift_detected": meta.get("drift_detected", []),
                "applied_aliases": meta.get("applied_aliases", {})
            })

    return {
        "webhook_id": webhook.id,
        "webhook_name": webhook.name,
        "recipe_name": recipe.name if recipe else "Receta",
        "total_executions": len(audit_records),
        "executions": audit_records
    }

# ----------------- Webhook Automations & Drops (Hardened) -----------------
@router.post("/automations")
def create_automation(
    req: CreateAutomationRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    recipe = db.query(Recipe).filter(Recipe.id == req.recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no pertenece al usuario.")

    token = f"wh_{uuid.uuid4().hex}"
    plain_secret = f"sec_{secrets.token_hex(24)}"
    encrypted_secret = encrypt_secret(plain_secret)
    preview = f"{plain_secret[:7]}...{plain_secret[-4:]}"

    webhook = AutomationWebhook(
        user_id=user.id,
        recipe_id=recipe.id,
        name=req.name,
        token=token,
        secret_key=encrypted_secret,
        secret_preview=preview,
        target_format=req.target_format
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return {
        "id": webhook.id,
        "name": webhook.name,
        "recipe_name": recipe.name,
        "token": webhook.token,
        "secret_key": plain_secret, # Returned ONCE upon creation
        "secret_preview": preview,
        "target_format": webhook.target_format,
        "webhook_url": f"/api/webhooks/drop/{webhook.token}",
        "created_at": webhook.created_at
    }

@router.get("/automations")
def list_automations(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    items = db.query(AutomationWebhook).filter(AutomationWebhook.user_id == user.id).order_by(AutomationWebhook.created_at.desc()).all()
    results = []
    for item in items:
        recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()
        results.append({
            "id": item.id,
            "name": item.name,
            "recipe_id": item.recipe_id,
            "recipe_name": recipe.name if recipe else "Receta",
            "token": item.token,
            "secret_preview": item.secret_preview or f"{decrypt_secret(item.secret_key)[:7]}...", # Masked: never expose full plain secret in list
            "target_format": item.target_format,
            "is_active": item.is_active,
            "runs_count": item.runs_count,
            "last_run_at": item.last_run_at,
            "webhook_url": f"/api/webhooks/drop/{item.token}",
            "created_at": item.created_at
        })
    return results

@router.delete("/automations/{automation_id}")
def delete_automation(
    automation_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    item = db.query(AutomationWebhook).filter(AutomationWebhook.id == automation_id, AutomationWebhook.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Automatización no encontrada o no autorizada.")
    db.delete(item)
    db.commit()
    return {"message": "Automatización eliminada."}

@router.post("/automations/{automation_id}/regenerate-secret")
def regenerate_webhook_secret(
    automation_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Regenerates webhook HMAC secret key securely and returns it once to the user.
    """
    item = db.query(AutomationWebhook).filter(AutomationWebhook.id == automation_id, AutomationWebhook.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Automatización no encontrada o no autorizada.")

    new_plain_secret = f"sec_{secrets.token_hex(24)}"
    item.secret_key = encrypt_secret(new_plain_secret)
    item.secret_preview = f"{new_plain_secret[:7]}...{new_plain_secret[-4:]}"
    db.commit()

    return {
        "id": item.id,
        "name": item.name,
        "token": item.token,
        "secret_key": new_plain_secret, # Returned ONCE upon regeneration
        "secret_preview": item.secret_preview
    }

@router.post("/webhooks/drop/{token}")
async def webhook_drop(
    token: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Hardened Webhook Drop Endpoint:
    1. Rate Limiting: max 30 req/min per webhook token to avoid denial of service.
    2. Lookup Webhook & check is_active.
    3. HMAC Authentication: verifies X-CleanSheet-Signature and timestamp against replay attacks.
       If secret_key is configured on the webhook, request MUST be signed.
    4. Validation: checks magic bytes, format, and maximum file size (25MB).
    5. Recipe Compatibility Check: ensures incoming structure matches recipe expectations.
    6. Unified Execution: runs via RecipeExecutionService.
    7. Clean Structured Logging: logs metadata (rows, size, duration) without logging sensitive row values.
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. Rate Limiting
    if not check_rate_limit(token):
        logger.warning(f"Rate limit exceeded on webhook token={token[:8]}... from ip={client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Límite de solicitudes superado (Rate limit: máximo 30 solicitudes por minuto para este webhook)."
        )

    # 2. Webhook lookup
    webhook = db.query(AutomationWebhook).filter(AutomationWebhook.token == token, AutomationWebhook.is_active == 1).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook no encontrado, token inválido o desactivado.")

    # 3. Read content and validate size/magic bytes
    content = await file.read()
    filename = file.filename or "archivo.xlsx"

    # 4. HMAC Signature Verification:
    sig_header = request.headers.get("X-CleanSheet-Signature") or request.headers.get("Signature")
    ts_header = request.headers.get("X-CleanSheet-Timestamp") or request.headers.get("Timestamp")
    nonce_header = request.headers.get("X-CleanSheet-Nonce") or request.headers.get("Idempotency-Key")

    if sig_header:
        plain_secret = decrypt_secret(webhook.secret_key)
        valid_sig, sig_err = verify_hmac_signature(
            secret_key=plain_secret,
            payload_bytes=content,
            signature_header=sig_header,
            timestamp_header=ts_header,
            nonce_header=nonce_header,
            webhook_token=token,
            max_drift_seconds=300
        )
        if not valid_sig:
            logger.warning(f"HMAC failure on webhook token={token[:8]}...: {sig_err}")
            raise HTTPException(status_code=401, detail=f"Autenticación HMAC fallida: {sig_err}")

    # 5. Validate file extension, magic bytes & size
    is_valid, ext, err_msg = validate_file_content(content, filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Archivo inválido: {err_msg}")

    # 6. Parse raw rows using unified service
    try:
        raw_rows = RecipeExecutionService.parse_raw_content(content, ext)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al analizar el contenido de la hoja: {str(e)}")

    if not raw_rows:
        raise HTTPException(status_code=400, detail="El archivo enviado no contiene filas legibles.")

    # 7. Unified Schema Compatibility & Structural Drift Evaluation
    recipe = db.query(Recipe).filter(Recipe.id == webhook.recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="La receta asociada a este webhook ya no existe.")

    recipe_dict = yaml.safe_load(recipe.definition_yaml)
    rules = recipe_dict.get("rules", {})

    analysis = NormalizationPlanner.plan(raw_rows)
    drift_res = SchemaCompatibilityService.evaluate(recipe_dict, analysis)

    if drift_res["is_blocking"]:
        logger.warning(f"Blocking drift on webhook drop token={token[:8]}...: {drift_res['drift_items']}")
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Ejecución detenida: se detectó un structural drift bloqueante respecto a la receta.",
                "drift_items": drift_res["drift_items"],
                "missing_columns": drift_res["missing_columns"]
            }
        )

    # 8. Merge applied aliases into execution rules
    execution_rules = dict(rules)
    if drift_res.get("applied_aliases"):
        execution_rules["column_aliases"] = recipe_dict.get("column_aliases", {})

    # Record operational metadata (safe, no cell values or secrets)
    op_meta = {
        "webhook_name": webhook.name,
        "token_prefix": f"{webhook.token[:8]}...",
        "hmac_status": "verified" if sig_header else "unsigned_accepted",
        "anti_replay_status": "passed_valid_nonce" if (sig_header and nonce_header) else "none",
        "schema_compatibility": drift_res["status"],
        "drift_detected": [item["message_es"] for item in drift_res.get("drift_items", [])],
        "applied_aliases": drift_res.get("applied_aliases", {}),
        "file_size_bytes": len(content)
    }

    # 9. Execute transformation via unified RecipeExecutionService
    exec_result = RecipeExecutionService.execute(
        raw_rows=raw_rows,
        rules=execution_rules,
        output_format=webhook.target_format,
        original_filename=filename,
        user_id=webhook.user_id,
        recipe_id=recipe.id,
        context_tag=f"webhook_{webhook.name}"
    )

    # 10. Update webhook stats and execution operational metadata in DB
    webhook.runs_count += 1
    webhook.last_run_at = datetime.now(timezone.utc)
    recipe.execution_count += 1
    recipe.last_used_at = datetime.now(timezone.utc)

    if exec_result.get("execution_id"):
        exec_record = db.query(Execution).filter(Execution.id == exec_result["execution_id"]).first()
        if exec_record:
            exec_record.result_metadata = op_meta

    db.commit()

    return FileResponse(
        storage.get_file_path(exec_result["storage_key"]),
        filename=exec_result["filename"],
        media_type=exec_result["media_type"]
    )
