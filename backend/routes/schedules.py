import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import zoneinfo

from models import (
    get_db, User, Recipe, ExternalStorageConnection,
    ScheduledAutomation, ScheduledRun
)
from auth import get_current_user_required
from scheduler_utils import calculate_next_runs, validate_target_path_template
from scheduler_dispatcher import SchedulerJobDispatcher
from object_selector import select_target_object
from connectors import get_connector
from crypto_service import decrypt_dict

logger = logging.getLogger("cleansheet.schedules")
router = APIRouter(prefix="/schedules", tags=["schedules"])

# ----------------- Request / Response Models -----------------

class CreateScheduleRequest(BaseModel):
    name: str
    recipe_id: str
    source_connection_id: str
    source_selector_type: Optional[str] = "exact" # exact | prefix | latest_matching
    source_key_pattern: str
    target_connection_id: Optional[str] = None
    target_path_strategy: Optional[str] = "templated"
    target_path_template: Optional[str] = "normalized/{source_stem}_{date}.{ext}"
    output_format: Optional[str] = "csv"
    schedule_type: Optional[str] = "daily" # daily | weekdays | weekly | monthly | cron
    cron_expression: Optional[str] = None
    timezone_name: Optional[str] = "Europe/Madrid"

class UpdateScheduleRequest(BaseModel):
    name: Optional[str] = None
    recipe_id: Optional[str] = None
    source_connection_id: Optional[str] = None
    source_selector_type: Optional[str] = None
    source_key_pattern: Optional[str] = None
    target_connection_id: Optional[str] = None
    target_path_strategy: Optional[str] = None
    target_path_template: Optional[str] = None
    output_format: Optional[str] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone_name: Optional[str] = None

class PreviewSelectorRequest(BaseModel):
    source_connection_id: str
    source_selector_type: str
    source_key_pattern: str

# ----------------- Endpoints -----------------

@router.post("")
def create_schedule(
    req: CreateScheduleRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    # 1. Ownership & Validation: Recipe
    recipe = db.query(Recipe).filter(Recipe.id == req.recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada o no pertenece al usuario.")

    # 2. Ownership & Validation: Source Connection
    source_conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == req.source_connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not source_conn:
        raise HTTPException(status_code=404, detail="Conector de origen no encontrado o no pertenece al usuario.")

    # 3. Ownership & Validation: Target Connection (optional, defaults to source)
    target_conn_id = req.target_connection_id or req.source_connection_id
    target_conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == target_conn_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not target_conn:
        raise HTTPException(status_code=404, detail="Conector de destino no encontrado o no pertenece al usuario.")

    # 4. Validate Path Template against Path Traversal
    is_safe_path, path_err = validate_target_path_template(req.target_path_template)
    if not is_safe_path:
        raise HTTPException(status_code=400, detail=path_err)

    # 5. Validate Timezone & Calculate next_run_at
    tz_name = (req.timezone_name or "UTC").strip()
    try:
        zoneinfo.ZoneInfo(tz_name)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Zona horaria no válida: '{tz_name}'. Usa una zona IANA (ej. 'Europe/Madrid', 'America/New_York', 'UTC').")

    try:
        next_runs = calculate_next_runs(
            schedule_type=req.schedule_type or "daily",
            cron_expr=req.cron_expression,
            timezone_name=tz_name,
            start_from_utc=datetime.now(timezone.utc),
            count=1
        )
        initial_next_run = next_runs[0] if next_runs else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en configuración de schedule: {str(e)}")

    automation = ScheduledAutomation(
        user_id=user.id,
        name=req.name.strip(),
        recipe_id=recipe.id,
        source_connection_id=source_conn.id,
        source_selector_type=req.source_selector_type or "exact",
        source_key_pattern=req.source_key_pattern.strip(),
        target_connection_id=target_conn.id,
        target_path_strategy=req.target_path_strategy or "templated",
        target_path_template=req.target_path_template.strip() if req.target_path_template else None,
        output_format=req.output_format or "csv",
        schedule_type=req.schedule_type or "daily",
        cron_expression=req.cron_expression.strip() if req.cron_expression else None,
        timezone_name=tz_name,
        is_active=1,
        next_run_at=initial_next_run
    )
    db.add(automation)
    db.commit()
    db.refresh(automation)

    return format_automation_response(automation, db)

@router.get("")
def list_schedules(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automations = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.user_id == user.id
    ).order_by(ScheduledAutomation.created_at.desc()).all()

    return [format_automation_response(a, db) for a in automations]

@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización programada no encontrada o no autorizada.")

    return format_automation_response(automation, db)

@router.patch("/{schedule_id}")
def update_schedule(
    schedule_id: str,
    req: UpdateScheduleRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización programada no encontrada o no autorizada.")

    # Validate updates
    if req.name is not None:
        automation.name = req.name.strip()
    if req.recipe_id is not None:
        recipe = db.query(Recipe).filter(Recipe.id == req.recipe_id, Recipe.user_id == user.id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail="Receta no encontrada.")
        automation.recipe_id = recipe.id
    if req.source_connection_id is not None:
        src = db.query(ExternalStorageConnection).filter(ExternalStorageConnection.id == req.source_connection_id, ExternalStorageConnection.user_id == user.id).first()
        if not src:
            raise HTTPException(status_code=404, detail="Conector origen no encontrado.")
        automation.source_connection_id = src.id
    if req.target_connection_id is not None:
        tgt = db.query(ExternalStorageConnection).filter(ExternalStorageConnection.id == req.target_connection_id, ExternalStorageConnection.user_id == user.id).first()
        if not tgt:
            raise HTTPException(status_code=404, detail="Conector destino no encontrado.")
        automation.target_connection_id = tgt.id

    if req.target_path_template is not None:
        is_safe, err = validate_target_path_template(req.target_path_template)
        if not is_safe:
            raise HTTPException(status_code=400, detail=err)
        automation.target_path_template = req.target_path_template.strip()

    if req.source_selector_type is not None:
        automation.source_selector_type = req.source_selector_type
    if req.source_key_pattern is not None:
        automation.source_key_pattern = req.source_key_pattern.strip()
    if req.output_format is not None:
        automation.output_format = req.output_format

    schedule_changed = False
    if req.schedule_type is not None:
        automation.schedule_type = req.schedule_type
        schedule_changed = True
    if req.cron_expression is not None:
        automation.cron_expression = req.cron_expression.strip() if req.cron_expression else None
        schedule_changed = True
    if req.timezone_name is not None:
        tz_name = req.timezone_name.strip()
        try:
            zoneinfo.ZoneInfo(tz_name)
            automation.timezone_name = tz_name
            schedule_changed = True
        except Exception:
            raise HTTPException(status_code=400, detail="Zona horaria no válida.")

    if schedule_changed and automation.is_active:
        next_runs = calculate_next_runs(
            schedule_type=automation.schedule_type,
            cron_expr=automation.cron_expression,
            timezone_name=automation.timezone_name,
            start_from_utc=datetime.now(timezone.utc),
            count=1
        )
        automation.next_run_at = next_runs[0] if next_runs else None

    db.commit()
    db.refresh(automation)
    return format_automation_response(automation, db)

@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización no encontrada o no autorizada.")

    db.delete(automation)
    db.commit()
    return {"message": "Automatización programada eliminada correctamente."}

@router.post("/{schedule_id}/enable")
def enable_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización no encontrada.")

    automation.is_active = 1
    next_runs = calculate_next_runs(
        schedule_type=automation.schedule_type,
        cron_expr=automation.cron_expression,
        timezone_name=automation.timezone_name,
        start_from_utc=datetime.now(timezone.utc),
        count=1
    )
    automation.next_run_at = next_runs[0] if next_runs else None
    db.commit()
    return {"message": "Automatización activada.", "is_active": 1, "next_run_at": automation.next_run_at.isoformat() if automation.next_run_at else None}

@router.post("/{schedule_id}/disable")
def disable_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización no encontrada.")

    automation.is_active = 0
    automation.next_run_at = None
    db.commit()
    return {"message": "Automatización pausada.", "is_active": 0}

@router.post("/{schedule_id}/run-now")
def run_schedule_now(
    schedule_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Executes automation immediately on demand.
    Reuses the exact same decoupled pipeline as scheduled runs.
    """
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización no encontrada.")

    # Check if a lease is currently active
    now_utc = datetime.now(timezone.utc)
    if automation.locked_until and automation.locked_until > now_utc:
        raise HTTPException(
            status_code=409,
            detail="La automatización está actualmente ejecutándose en otro proceso. Espera a que termine."
        )

    # Claim temporary lock
    automation.locked_until = now_utc + zoneinfo.timedelta(seconds=120) if hasattr(zoneinfo, "timedelta") else now_utc + datetime.resolution * 120
    db.commit()

    try:
        result = SchedulerJobDispatcher.execute_job(
            db=db,
            automation=automation,
            scheduled_for=now_utc,
            trigger_type="manual"
        )
        return result
    finally:
        automation.locked_until = None
        db.commit()

@router.get("/{schedule_id}/runs")
def list_schedule_runs(
    schedule_id: str,
    limit: int = 30,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    Retrieves execution history for a specific scheduled automation with ownership isolation.
    """
    automation = db.query(ScheduledAutomation).filter(
        ScheduledAutomation.id == schedule_id,
        ScheduledAutomation.user_id == user.id
    ).first()
    if not automation:
        raise HTTPException(status_code=404, detail="Automatización no encontrada.")

    runs = db.query(ScheduledRun).filter(
        ScheduledRun.automation_id == automation.id
    ).order_by(ScheduledRun.started_at.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "scheduled_for": r.scheduled_for.isoformat() if r.scheduled_for else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "trigger_type": r.trigger_type,
            "skip_reason": r.skip_reason,
            "error_message": r.error_message,
            "source_key": r.source_key,
            "source_etag": r.source_etag,
            "target_key": r.target_key,
            "rows_in": r.rows_in,
            "rows_out": r.rows_out,
            "duration_ms": r.duration_ms,
            "schema_status": r.schema_status,
            "drift_items": r.drift_items,
            "applied_aliases": r.applied_aliases,
            "execution_id": r.execution_id
        }
        for r in runs
    ]

@router.post("/preview-selector")
def preview_source_selector(
    req: PreviewSelectorRequest,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """
    UI Helper: inspects which object in the source bucket would be picked by the selector pattern.
    """
    source_conn = db.query(ExternalStorageConnection).filter(
        ExternalStorageConnection.id == req.source_connection_id,
        ExternalStorageConnection.user_id == user.id
    ).first()
    if not source_conn:
        raise HTTPException(status_code=404, detail="Conector origen no encontrado.")

    config = decrypt_dict(source_conn.encrypted_config)
    try:
        connector = get_connector(source_conn.provider_type, config)
        selected = select_target_object(connector, req.source_selector_type, req.source_key_pattern)
        if not selected:
            return {
                "matched": False,
                "message": f"No se encontró ningún objeto compatible que coincida con '{req.source_key_pattern}'."
            }
        return {
            "matched": True,
            "object": {
                "key": selected.key,
                "size_bytes": selected.size_bytes,
                "etag": selected.etag,
                "last_modified": selected.last_modified.isoformat() if selected.last_modified else None
            }
        }
    except Exception as e:
        return {"matched": False, "message": str(e)}

# ----------------- Helper Formatter -----------------

def format_automation_response(a: ScheduledAutomation, db: Session) -> Dict[str, Any]:
    # Check if resources are missing -> mark status as needs_attention
    is_invalid = False
    invalid_reason = None
    if not a.recipe_id or not a.recipe:
        is_invalid = True
        invalid_reason = "La receta configurada ya no existe."
    elif not a.source_connection_id or not a.source_connection:
        is_invalid = True
        invalid_reason = "El conector de origen configurado ya no existe."

    effective_status = "needs_attention" if is_invalid else (a.last_status or "idle")

    # Calculate preview of next 3 execution dates
    next_3_dates = []
    if a.is_active and not is_invalid:
        try:
            dates = calculate_next_runs(
                schedule_type=a.schedule_type,
                cron_expr=a.cron_expression,
                timezone_name=a.timezone_name,
                start_from_utc=datetime.now(timezone.utc),
                count=3
            )
            next_3_dates = [d.isoformat() for d in dates]
        except Exception:
            pass

    return {
        "id": a.id,
        "name": a.name,
        "recipe_id": a.recipe_id,
        "recipe_name": a.recipe.name if a.recipe else "No encontrada",
        "source_connection_id": a.source_connection_id,
        "source_connection_name": a.source_connection.name if a.source_connection else "No encontrado",
        "source_selector_type": a.source_selector_type,
        "source_key_pattern": a.source_key_pattern,
        "target_connection_id": a.target_connection_id,
        "target_connection_name": a.target_connection.name if a.target_connection else (a.source_connection.name if a.source_connection else "No encontrado"),
        "target_path_strategy": a.target_path_strategy,
        "target_path_template": a.target_path_template,
        "output_format": a.output_format,
        "schedule_type": a.schedule_type,
        "cron_expression": a.cron_expression,
        "timezone_name": a.timezone_name,
        "is_active": a.is_active,
        "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
        "next_run_at": a.next_run_at.isoformat() if a.next_run_at else (next_3_dates[0] if next_3_dates else None),
        "next_3_runs": next_3_dates,
        "last_status": effective_status,
        "last_error": invalid_reason or a.last_error,
        "consecutive_failures": a.consecutive_failures,
        "is_invalid": is_invalid,
        "created_at": a.created_at.isoformat() if a.created_at else None
    }
