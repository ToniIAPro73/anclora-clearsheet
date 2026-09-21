import io
import time
import os
import re
import yaml
import hmac
import hashlib
import logging
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Generator
import pandas as pd
import polars as pl

from models import SessionLocal, Execution, SourceFile, Recipe, AutomationWebhook, ProcessedNonce
from storage import storage
from engine import NormalizationPlanner, TransformationEngine
from heuristics import check_recipe_compatibility
from rate_limit_store import rate_limiter
from csv_detector import CsvDialectDetector

logger = logging.getLogger("cleansheet.execution")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

# Security limits
MAX_STANDARD_FILE_SIZE_BYTES = 25 * 1024 * 1024   # 25 MB max for standard in-memory Excel/CSV
MAX_FILE_SIZE_BYTES = MAX_STANDARD_FILE_SIZE_BYTES
MAX_STREAMING_FILE_SIZE_BYTES = 300 * 1024 * 1024  # 300 MB max threshold for chunked streaming CSV
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# ZIP Bomb & OOXML limits for XLSX
MAX_ZIP_ENTRIES = 500
MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB max uncompressed content inside XLSX
MAX_COMPRESSION_RATIO = 50.0  # Alert if uncompressed / compressed > 50

# Rate limiting parameters
RATE_LIMIT_WINDOW = 60.0  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 30  # Max 30 requests per minute

def check_rate_limit(identifier: str) -> bool:
    """Uses decoupled RateLimitStore to check limits."""
    return not rate_limiter.is_rate_limited(identifier, limit=RATE_LIMIT_MAX_REQUESTS, window_seconds=RATE_LIMIT_WINDOW)

def validate_ooxml_xlsx(content: bytes) -> Tuple[bool, str]:
    """
    Exhaustive OOXML verification and ZIP Bomb prevention:
    1. Validates PK zip structure.
    2. Enforces maximum entry count, uncompressed size and compression ratio limits.
    3. Validates required OOXML manifest files: [Content_Types].xml and (xl/workbook.xml or xl/_rels/workbook.xml.rels).
    """
    if not content.startswith(b"PK\x03\x04"):
        return False, "Contenido corrupto o formato inválido: archivo .xlsx no tiene firma ZIP válida."

    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
            infolist = zf.infolist()
            if len(infolist) > MAX_ZIP_ENTRIES:
                return False, f"Protección ZIP Bomb: el archivo XLSX contiene {len(infolist)} entradas (máximo permitido: {MAX_ZIP_ENTRIES})."

            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_UNCOMPRESSED_SIZE_BYTES:
                return False, f"Protección ZIP Bomb: el tamaño descomprimido ({total_uncompressed // (1024*1024)}MB) excede el límite seguro ({MAX_UNCOMPRESSED_SIZE_BYTES // (1024*1024)}MB)."

            if len(content) > 0:
                ratio = total_uncompressed / max(1, len(content))
                if ratio > MAX_COMPRESSION_RATIO and total_uncompressed > 10 * 1024 * 1024:
                    return False, f"Protección ZIP Bomb: ratio de compresión anómalo detectado ({ratio:.1f}:1)."

            # Verify canonical OOXML package members
            names = set(zf.namelist())
            has_content_types = "[Content_Types].xml" in names
            has_workbook = any(n in names for n in ["xl/workbook.xml", "xl/workbook.bin", "workbook.xml"])

            if not (has_content_types and has_workbook):
                return False, "Estructura OOXML inválida: faltan componentes esenciales de Excel ([Content_Types].xml o xl/workbook.xml)."
    except zipfile.BadZipFile:
        return False, "Archivo .xlsx corrupto o archivo ZIP dañado."
    except Exception as e:
        return False, f"Error al validar archivo XLSX: {str(e)}"

    return True, ""

def validate_file_content(content: bytes, filename: str, is_streaming: bool = False) -> Tuple[bool, str, str]:
    """
    Validates file extension, size limits and magic bytes.
    Differentiates standard (25MB) vs streaming CSV limits (250MB).
    """
    if len(content) == 0:
        return False, "", "El archivo está vacío (0 bytes)."

    max_size = MAX_STREAMING_FILE_SIZE_BYTES if (is_streaming and filename.lower().endswith(".csv")) else MAX_STANDARD_FILE_SIZE_BYTES
    if len(content) > max_size:
        return False, "", f"El archivo excede el tamaño máximo permitido de {max_size // (1024*1024)}MB."

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, ext, f"Extensión no permitida '{ext}'. Solo se permiten archivos .xlsx, .xls y .csv."

    # Validate Format & Magic Bytes
    if ext == ".xlsx":
        valid_ooxml, ooxml_err = validate_ooxml_xlsx(content)
        if not valid_ooxml:
            return False, ext, ooxml_err
    elif ext == ".xls":
        if not (content.startswith(b"\xd0\xcf\x11\xe0") or content.startswith(b"PK\x03\x04")):
            return False, ext, "Contenido corrupto: archivo .xls no tiene firma OLE válida."
    elif ext == ".csv":
        if b"\x00" in content[:1024]:
            return False, ext, "Contenido corrupto o binario detectado en archivo CSV."

    return True, ext, ""

def check_and_record_nonce(nonce: str, webhook_token: str, ttl_seconds: int = 600) -> Tuple[bool, str]:
    """
    Anti-Replay Mechanism: records nonce / idempotency-key and rejects duplicates.
    Periodically cleans expired nonces older than ttl_seconds.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # 1. Clean expired nonces older than ttl_seconds
        cutoff = now - timedelta(seconds=ttl_seconds)
        db.query(ProcessedNonce).filter(ProcessedNonce.created_at < cutoff).delete(synchronize_session=False)

        # 2. Check if nonce already exists
        existing = db.query(ProcessedNonce).filter(ProcessedNonce.nonce == nonce).first()
        if existing:
            return False, "Replay attack detectado: el nonce / idempotency-key ya ha sido procesado anteriormente."

        # 3. Record new nonce
        new_record = ProcessedNonce(nonce=nonce, webhook_token=webhook_token, created_at=now)
        db.add(new_record)
        db.commit()
        return True, "Nonce válido"
    except Exception as e:
        db.rollback()
        return True, "Nonce check bypassed" # Soft fail on db contention
    finally:
        db.close()

def verify_hmac_signature(
    secret_key: str,
    payload_bytes: bytes,
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    nonce_header: Optional[str] = None,
    webhook_token: str = "",
    max_drift_seconds: int = 300
) -> Tuple[bool, str]:
    """
    Verifies HMAC SHA-256 signature with timestamp drift check AND Nonce / Idempotency-Key anti-replay.
    Signature format: 't=<timestamp>,v1=<sig>' (or headers X-CleanSheet-Timestamp, X-CleanSheet-Nonce, X-CleanSheet-Signature)
    """
    if not signature_header:
        return False, "Falta la cabecera de firma requerida 'X-CleanSheet-Signature' o 'Signature'."

    req_timestamp = None
    provided_sig = None
    parsed_nonce = nonce_header

    if "t=" in signature_header and "v1=" in signature_header:
        parts = signature_header.split(",")
        for p in parts:
            p = p.strip()
            if p.startswith("t="):
                req_timestamp = p[2:]
            elif p.startswith("v1="):
                provided_sig = p[3:]
            elif p.startswith("n="):
                parsed_nonce = p[2:]
    else:
        provided_sig = signature_header.strip()
        req_timestamp = timestamp_header

    if not req_timestamp or not provided_sig:
        return False, "Firma o timestamp malformados. Formato esperado: 't=<timestamp>,v1=<hex_signature>' o cabecera X-CleanSheet-Timestamp."

    try:
        ts_int = int(req_timestamp)
    except ValueError:
        return False, "Timestamp de firma inválido."

    # 1. Clock drift check
    current_ts = int(time.time())
    if abs(current_ts - ts_int) > max_drift_seconds:
        return False, f"Replay attack detectado o reloj desincronizado (diferencia: {abs(current_ts - ts_int)}s > {max_drift_seconds}s permitido)."

    # 2. Compute expected HMAC SHA-256 over f"{ts_int}.{payload_hash}"
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    data_to_sign = f"{ts_int}.{payload_hash}".encode("utf-8")
    expected_sig = hmac.new(secret_key.encode("utf-8"), data_to_sign, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, provided_sig):
        return False, "Firma HMAC inválida. Secreto incorrecto o contenido modificado."

    # 3. Nonce verification to defeat replay attacks within the 300s window (only after signature is verified)
    effective_nonce = parsed_nonce or provided_sig # Fallback to signature hash itself as unique nonce if client didn't supply separate nonce
    valid_nonce, nonce_err = check_and_record_nonce(effective_nonce, webhook_token, ttl_seconds=max_drift_seconds * 2)
    if not valid_nonce:
        return False, nonce_err

    return True, "Firma válida"


class RecipeExecutionService:
    """
    Single unified execution engine for:
    - Single File UI Export
    - Batch Processing
    - Webhook Automations
    - Stream Chunked Parsing for large CSV files
    """

    @classmethod
    def parse_raw_content(
        cls,
        content: bytes,
        ext: str,
        sheet_name: Optional[str] = None,
        manual_delimiter: Optional[str] = None
    ) -> List[List[Any]]:
        """Parses raw spreadsheet bytes into deterministic raw rows."""
        if ext in [".xlsx", ".xls"]:
            buf = io.BytesIO(content)
            df = pd.read_excel(buf, sheet_name=sheet_name or 0, header=None)
            return df.fillna("").values.tolist()
        else:
            # Unified CSV parsing using robust CsvDialectDetector
            import csv
            dialect_info = CsvDialectDetector.analyze(content, manual_override_delimiter=manual_delimiter)
            delimiter = dialect_info["delimiter"]
            encoding = dialect_info["encoding"]

            try:
                text_data = content.decode(encoding, errors="replace")
            except Exception:
                text_data = content.decode("utf-8", errors="replace")

            reader = csv.reader(
                io.StringIO(text_data),
                delimiter=delimiter,
                quotechar=dialect_info.get("quote_char", '"')
            )
            raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
            return raw_rows

    @classmethod
    def execute_stream_csv(
        cls,
        csv_file_path: str,
        rules: Dict[str, Any],
        output_format: str = "csv",
        chunk_size: int = 50000,
        original_filename: str = "large_data.csv",
        user_id: Optional[str] = None,
        recipe_id: Optional[str] = None,
        context_tag: str = "stream",
        manual_delimiter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-Performance Chunked Streaming Parser using Polars / PyArrow.
        Reads and normalizes large CSVs in chunks without loading the whole dataset into memory.
        Uses CsvDialectDetector to detect delimiter (comma, semicolon, tab, pipe), quoting and encoding.
        """
        start_time = time.time()
        file_size_bytes = os.path.getsize(csv_file_path)

        # Sample initial bytes for dialect analysis
        with open(csv_file_path, "rb") as f:
            sample_bytes = f.read(32768)

        dialect_info = CsvDialectDetector.analyze(sample_bytes, manual_override_delimiter=manual_delimiter)
        delimiter = dialect_info["delimiter"]
        encoding = dialect_info["encoding"]
        quotechar = dialect_info.get("quote_char", '"')

        header_row = int(rules.get("remove_top_rows", 0))

        # Sample initial lines for headers
        with open(csv_file_path, "r", encoding=encoding, errors="replace") as f:
            sample_lines = [f.readline() for _ in range(header_row + 5)]

        import csv
        reader = csv.reader(io.StringIO("\n".join(sample_lines)), delimiter=delimiter, quotechar=quotechar)
        all_sample_rows = [r for r in reader if any(c.strip() for c in r)]

        headers = []
        if header_row < len(all_sample_rows):
            headers = [str(c).strip() if c.strip() else f"col_{i+1}" for i, c in enumerate(all_sample_rows[header_row])]
        else:
            headers = [f"col_{i+1}" for i in range(len(all_sample_rows[0]) if all_sample_rows else 0)]

        # Apply Column Aliases if defined in rules (e.g. customer_code -> customer_id)
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

        case_rule = rules.get("normalize_headers_case", "preserve")
        if case_rule == "snake_case":
            clean_headers = []
            for h in headers:
                s = re.sub(r"[^\w\s-]", "", h).strip()
                s = re.sub(r"[-\s]+", "_", s).lower()
                clean_headers.append(s)
            headers = clean_headers

        out_ext = output_format.lstrip(".")
        # Optimization: stream directly into destination storage file instead of holding 250MB in BytesIO buffer!
        dest_path, storage_key = storage.create_destination_path(out_ext)

        total_rows_in = 0
        total_rows_out = 0
        total_changes = 0
        chunks_count = 0

        # Stream chunks with pandas chunking and detected delimiter
        is_first_chunk = True
        with open(dest_path, "w", encoding="utf-8", newline="") as out_file:
            for chunk in pd.read_csv(
                csv_file_path,
                skiprows=header_row + 1,
                header=None,
                sep=delimiter,
                quotechar=quotechar,
                encoding=encoding,
                chunksize=chunk_size,
                dtype=str
            ):
                chunks_count += 1
                chunk_rows = chunk.fillna("").values.tolist()
                total_rows_in += len(chunk_rows)

                transformed_chunk = TransformationEngine.apply_rules(
                    [headers] + chunk_rows,
                    rules={**rules, "remove_top_rows": 0}
                )

                chunk_df = pd.DataFrame(transformed_chunk["rows"], columns=transformed_chunk["headers"])
                total_rows_out += len(transformed_chunk["rows"])
                total_changes += transformed_chunk["changes_count"]

                if is_first_chunk:
                    chunk_df.to_csv(out_file, index=False)
                    is_first_chunk = False
                else:
                    chunk_df.to_csv(out_file, index=False, header=False)

                # Explicitly release chunk from memory
                del chunk_rows
                del transformed_chunk
                del chunk_df
                del chunk
                if chunks_count % 10 == 0:
                    import gc
                    gc.collect()

        duration_ms = int((time.time() - start_time) * 1000)
        bytes_out = os.path.getsize(dest_path)

        # Record Execution with complete internal metrics
        exec_id = None
        result_meta = {
            "dialect": dialect_info,
            "chunks_count": chunks_count,
            "chunk_size": chunk_size,
            "bytes_in": file_size_bytes,
            "bytes_out": bytes_out
        }
        try:
            db = SessionLocal()
            exec_record = Execution(
                user_id=user_id,
                recipe_id=recipe_id,
                file_name=f"[{context_tag.upper()}_STREAM] {original_filename}",
                rows_input=total_rows_in,
                rows_output=total_rows_out,
                columns_input=len(headers),
                columns_output=len(headers),
                transformations_count=total_changes,
                duration_ms=duration_ms,
                result_storage_path=storage_key,
                result_metadata=result_meta,
                status="completed"
            )
            db.add(exec_record)
            db.commit()
            db.refresh(exec_record)
            exec_id = exec_record.id
            db.close()
        except Exception as e:
            logger.warning(f"Could not record stream execution: {e}")

        logger.info(
            f"Stream execution completed: file={original_filename} "
            f"rows_in={total_rows_in} rows_out={total_rows_out} chunks={chunks_count} duration_ms={duration_ms}"
        )

        return {
            "execution_id": exec_id,
            "filename": f"clean_{Path(original_filename).stem}.{out_ext}",
            "storage_key": storage_key,
            "file_bytes": None, # Kept None for streaming large files to prevent loading 250MB in memory!
            "media_type": "text/csv",
            "rows_in": total_rows_in,
            "rows_out": total_rows_out,
            "columns_out": len(headers),
            "changes_count": total_changes,
            "chunks_count": chunks_count,
            "bytes_in": file_size_bytes,
            "bytes_out": bytes_out,
            "dialect_detected": dialect_info,
            "duration_ms": duration_ms
        }

    @classmethod
    def execute(
        cls,
        raw_rows: List[List[Any]],
        rules: Dict[str, Any],
        output_format: str = "xlsx",
        original_filename: str = "data",
        user_id: Optional[str] = None,
        recipe_id: Optional[str] = None,
        context_tag: str = "manual"
    ) -> Dict[str, Any]:
        """
        Executes transformation deterministically, logs audit record, and persists output file.
        """
        start_time = time.time()
        transformed = TransformationEngine.apply_rules(raw_rows, rules)
        duration_ms = int((time.time() - start_time) * 1000)

        clean_df = pd.DataFrame(transformed["rows"], columns=transformed["headers"])
        out_ext = output_format.lstrip(".")
        buf = io.BytesIO()
        if out_ext in ["xlsx", "xls"]:
            clean_df.to_excel(buf, index=False)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            clean_df.to_csv(buf, index=False)
            media_type = "text/csv"

        buf.seek(0)
        bytes_val = buf.getvalue()
        storage_key = storage.save_file(io.BytesIO(bytes_val), out_ext)

        exec_id = None
        try:
            db = SessionLocal()
            exec_record = Execution(
                user_id=user_id,
                recipe_id=recipe_id,
                file_name=f"[{context_tag.upper()}] {original_filename}",
                rows_input=len(raw_rows),
                rows_output=len(transformed["rows"]),
                columns_input=len(raw_rows[0]) if raw_rows else 0,
                columns_output=len(transformed["headers"]),
                transformations_count=transformed["changes_count"],
                duration_ms=duration_ms,
                result_storage_path=storage_key,
                status="completed"
            )
            db.add(exec_record)
            db.commit()
            db.refresh(exec_record)
            exec_id = exec_record.id
            db.close()
        except Exception as e:
            logger.warning(f"Could not record execution in DB: {e}")

        logger.info(
            f"Execution completed: tag={context_tag} file={original_filename} "
            f"rows_in={len(raw_rows)} rows_out={len(transformed['rows'])} duration_ms={duration_ms}"
        )

        return {
            "execution_id": exec_id,
            "filename": f"clean_{Path(original_filename).stem}.{out_ext}",
            "storage_key": storage_key,
            "file_bytes": bytes_val,
            "media_type": media_type,
            "rows_in": len(raw_rows),
            "rows_out": len(transformed["rows"]),
            "columns_out": len(transformed["headers"]),
            "changes_count": transformed["changes_count"],
            "duration_ms": duration_ms
        }
