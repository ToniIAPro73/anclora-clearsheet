import os
import io
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import yaml

from models import (
    ScheduledAutomation, ScheduledRun, Execution,
    Recipe, ExternalStorageConnection, SessionLocal
)
from connectors import get_connector
from crypto_service import decrypt_dict
from object_selector import select_target_object
from schema_validator import SchemaCompatibilityService
from engine import NormalizationPlanner
from recipe_service import RecipeExecutionService
from scheduler_utils import calculate_next_runs

logger = logging.getLogger("cleansheet.scheduler")

# Transient errors that are eligible for retry
TRANSIENT_ERROR_SUBSTRINGS = [
    "connection reset", "timeout", "timed out", "temporarily unavailable",
    "service unavailable", "503", "502", "504", "endpointconnectionerror",
    "rate limit", "too many requests", "retryable"
]

def is_transient_error(err_str: str) -> bool:
    lower = err_str.lower()
    return any(sub in lower for sub in TRANSIENT_ERROR_SUBSTRINGS)

class SchedulerJobDispatcher:
    """
    Executes a scheduled automation run through the strict unified pipeline:
    ScheduledRun -> ExternalStorageConnector -> SchemaCompatibilityService -> RecipeExecutionService -> Target S3 -> Execution
    """

    @classmethod
    def execute_job(
        cls,
        db: Session,
        automation: ScheduledAutomation,
        scheduled_for: datetime,
        trigger_type: str = "scheduled"
    ) -> Dict[str, Any]:
        """
        Executes a job with idempotency and distributed lease tracking.
        """
        # 1. Idempotency Check: check if a ScheduledRun already exists for this (automation_id, scheduled_for)
        existing_run = db.query(ScheduledRun).filter(
            ScheduledRun.automation_id == automation.id,
            ScheduledRun.scheduled_for == scheduled_for
        ).first()

        if existing_run and existing_run.status == "completed":
            logger.info(f"Skipping job: ScheduledRun for automation={automation.id} at {scheduled_for} already completed.")
            return {
                "status": "skipped",
                "reason": "already_executed_idempotent",
                "run_id": existing_run.id
            }

        # 2. Check if the automation configuration references valid, active resources
        if not automation.recipe_id or not automation.recipe:
            automation.last_status = "needs_attention"
            automation.last_error = "Receta asociada eliminada o no disponible."
            db.commit()
            return {"status": "needs_attention", "error": automation.last_error}

        if not automation.source_connection_id or not automation.source_connection:
            automation.last_status = "needs_attention"
            automation.last_error = "Conector de origen eliminado o no disponible."
            db.commit()
            return {"status": "needs_attention", "error": automation.last_error}

        target_conn = automation.target_connection or automation.source_connection

        # 3. Create or update ScheduledRun record to 'running'
        if not existing_run:
            scheduled_run = ScheduledRun(
                automation_id=automation.id,
                scheduled_for=scheduled_for,
                trigger_type=trigger_type,
                started_at=datetime.now(timezone.utc),
                status="running",
                attempt_count=1
            )
            db.add(scheduled_run)
        else:
            scheduled_run = existing_run
            scheduled_run.started_at = datetime.now(timezone.utc)
            scheduled_run.status = "running"
            scheduled_run.attempt_count += 1

        db.commit()
        db.refresh(scheduled_run)

        start_time = time.time()
        try:
            # 4. Connect to Source
            src_config = decrypt_dict(automation.source_connection.encrypted_config)
            src_connector = get_connector(automation.source_connection.provider_type, src_config)

            # 5. Select Source Object
            selected_obj = select_target_object(
                connector=src_connector,
                selector_type=automation.source_selector_type,
                pattern=automation.source_key_pattern
            )

            if not selected_obj:
                msg = f"No se encontró ningún objeto compatible en origen con el criterio '{automation.source_selector_type}' y patrón '{automation.source_key_pattern}'."
                scheduled_run.status = "skipped"
                scheduled_run.skip_reason = "source_object_not_found"
                scheduled_run.error_message = msg
                scheduled_run.finished_at = datetime.now(timezone.utc)
                automation.last_status = "skipped"
                automation.last_error = msg
                db.commit()
                return {"status": "skipped", "reason": msg, "run_id": scheduled_run.id}

            # 6. Deduplication Check: avoid silently reprocessing unchanged file (key + etag + version)
            version_id = getattr(selected_obj, "version_id", None)
            is_same_file = (
                automation.last_processed_object_key == selected_obj.key and
                automation.last_processed_etag == selected_obj.etag and
                (version_id is None or automation.last_processed_version_id == version_id)
            )

            if is_same_file and trigger_type == "scheduled":
                msg = f"El objeto '{selected_obj.key}' ya fue procesado anteriormente con el mismo ETag ({selected_obj.etag}). Omitiendo reproceso."
                scheduled_run.status = "skipped"
                scheduled_run.skip_reason = "source_object_already_processed"
                scheduled_run.source_key = selected_obj.key
                scheduled_run.source_etag = selected_obj.etag
                scheduled_run.source_version_id = version_id
                scheduled_run.finished_at = datetime.now(timezone.utc)
                automation.last_status = "skipped"
                automation.last_error = msg
                db.commit()
                return {"status": "skipped", "reason": msg, "run_id": scheduled_run.id}

            # 7. Stream content into temp buffer
            temp_dir = Path("/tmp/cleansheet_scheduled_runs")
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"run_{scheduled_run.id}_{Path(selected_obj.key).name}"

            with open(temp_file, "wb") as f_out:
                for chunk in src_connector.read_stream(selected_obj.key):
                    f_out.write(chunk)

            ext = Path(selected_obj.key).suffix.lower()
            with open(temp_file, "rb") as f_in:
                file_bytes = f_in.read()

            raw_rows = RecipeExecutionService.parse_raw_content(file_bytes, ext)
            if not raw_rows:
                raise ValueError("El archivo seleccionado está vacío o no contiene filas interpretables.")

            # 8. Schema Compatibility & Drift Evaluation
            recipe_dict = yaml.safe_load(automation.recipe.definition_yaml)
            rules = recipe_dict.get("rules", {})

            analysis = NormalizationPlanner.plan(raw_rows)
            drift_res = SchemaCompatibilityService.evaluate(recipe_dict, analysis)

            scheduled_run.schema_status = drift_res["status"]
            scheduled_run.drift_items = drift_res.get("drift_items", [])
            scheduled_run.applied_aliases = drift_res.get("applied_aliases", {})

            # Blocking drift halts transformation deterministically
            if drift_res["is_blocking"]:
                err_msg = f"Structural drift bloqueante detectado: columnas requeridas ausentes {drift_res.get('missing_columns', [])}."
                scheduled_run.status = "failed"
                scheduled_run.error_message = err_msg
                scheduled_run.finished_at = datetime.now(timezone.utc)
                automation.last_status = "failed"
                automation.last_error = err_msg
                automation.consecutive_failures += 1
                db.commit()
                return {"status": "failed", "error": err_msg, "run_id": scheduled_run.id}

            # Merge applied aliases into execution rules
            execution_rules = dict(rules)
            if drift_res.get("applied_aliases"):
                execution_rules["column_aliases"] = recipe_dict.get("column_aliases", {})

            # 9. Execute Deterministic Transformation
            out_format = automation.output_format or "csv"
            exec_result = RecipeExecutionService.execute(
                raw_rows=raw_rows,
                rules=execution_rules,
                output_format=out_format,
                original_filename=Path(selected_obj.key).name,
                user_id=automation.user_id,
                recipe_id=automation.recipe.id,
                context_tag=f"scheduled_{automation.name}"
            )

            # 10. Write to Target S3
            tgt_config = decrypt_dict(target_conn.encrypted_config)
            tgt_connector = get_connector(target_conn.provider_type, tgt_config)

            # Build target key based on strategy and template
            src_stem = Path(selected_obj.key).stem
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            if automation.target_path_template and automation.target_path_template.strip():
                target_key = automation.target_path_template.format(
                    source_stem=src_stem,
                    date=date_str,
                    ext=out_format
                )
            else:
                target_key = f"normalized/{src_stem}_clean.{out_format}"

            target_buf = io.BytesIO(exec_result["file_bytes"])
            tgt_write_meta = tgt_connector.write_stream(
                key=target_key,
                stream=target_buf,
                content_type=exec_result["media_type"]
            )

            duration_total_ms = int((time.time() - start_time) * 1000)

            # 11. Record Run and Update Automation State
            scheduled_run.status = "completed"
            scheduled_run.execution_id = exec_result.get("execution_id")
            scheduled_run.source_key = selected_obj.key
            scheduled_run.source_etag = selected_obj.etag
            scheduled_run.source_version_id = version_id
            scheduled_run.target_key = target_key
            scheduled_run.rows_in = exec_result["rows_in"]
            scheduled_run.rows_out = exec_result["rows_out"]
            scheduled_run.duration_ms = duration_total_ms
            scheduled_run.finished_at = datetime.now(timezone.utc)

            # Update cache on automation
            automation.last_run_at = datetime.now(timezone.utc)
            automation.last_status = "completed"
            automation.last_error = None
            automation.consecutive_failures = 0
            automation.last_processed_object_key = selected_obj.key
            automation.last_processed_etag = selected_obj.etag
            automation.last_processed_version_id = version_id
            automation.last_processed_timestamp = datetime.now(timezone.utc)

            # Update execution record details
            if exec_result.get("execution_id"):
                ex_record = db.query(Execution).filter(Execution.id == exec_result["execution_id"]).first()
                if ex_record:
                    ex_record.file_name = f"[SCHEDULED] {Path(selected_obj.key).name} -> {Path(target_key).name}"
                    ex_record.result_metadata = {
                        "automation_id": automation.id,
                        "automation_name": automation.name,
                        "scheduled_for": scheduled_for.isoformat(),
                        "trigger_type": trigger_type,
                        "source_key": selected_obj.key,
                        "source_etag": selected_obj.etag,
                        "target_key": target_key,
                        "schema_status": drift_res["status"],
                        "drift_detected": [d.get("message_es") for d in drift_res.get("drift_items", [])],
                        "applied_aliases": drift_res.get("applied_aliases", {})
                    }

            db.commit()
            temp_file.unlink(missing_ok=True)

            return {
                "status": "completed",
                "run_id": scheduled_run.id,
                "execution_id": exec_result.get("execution_id"),
                "source_key": selected_obj.key,
                "target_key": target_key,
                "rows_in": exec_result["rows_in"],
                "rows_out": exec_result["rows_out"],
                "duration_ms": duration_total_ms
            }

        except Exception as e:
            duration_total_ms = int((time.time() - start_time) * 1000)
            err_msg = str(e)
            # Sanitize error to avoid credential leak
            clean_err = err_msg.replace(str(automation.source_connection.encrypted_config or ""), "[REDACTED]")

            scheduled_run.status = "failed"
            scheduled_run.error_message = clean_err
            scheduled_run.duration_ms = duration_total_ms
            scheduled_run.finished_at = datetime.now(timezone.utc)

            automation.last_status = "failed"
            automation.last_error = clean_err
            automation.consecutive_failures += 1
            db.commit()

            return {
                "status": "failed",
                "run_id": scheduled_run.id,
                "error": clean_err,
                "is_transient": is_transient_error(clean_err)
            }
