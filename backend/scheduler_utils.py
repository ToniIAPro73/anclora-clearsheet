import re
import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from croniter import croniter

# Allowed common schedule types
SCHEDULE_TYPES = ["daily", "weekdays", "weekly", "monthly", "cron"]

def get_cron_expression(schedule_type: str, custom_cron: Optional[str] = None) -> str:
    """
    Maps high-level schedule types to standard 5-part cron expressions.
    Runs daily/weekdays/weekly at 08:00 (local time).
    """
    if schedule_type == "daily":
        return "0 8 * * *" # Every day at 08:00
    elif schedule_type == "weekdays":
        return "0 8 * * 1-5" # Mon-Fri at 08:00
    elif schedule_type == "weekly":
        return "0 8 * * 1" # Mondays at 08:00
    elif schedule_type == "monthly":
        return "0 8 1 * *" # 1st of every month at 08:00
    elif schedule_type == "cron":
        if not custom_cron or not custom_cron.strip():
            raise ValueError("Expresión cron personalizada requerida.")
        clean = custom_cron.strip()
        if not croniter.is_valid(clean):
            raise ValueError(f"Expresión cron inválida: '{clean}'")
        return clean
    else:
        raise ValueError(f"Tipo de frecuencia no soportado: '{schedule_type}'")

def calculate_next_runs(
    schedule_type: str,
    cron_expr: Optional[str],
    timezone_name: str,
    start_from_utc: Optional[datetime] = None,
    count: int = 3
) -> List[datetime]:
    """
    Calculates the next 'count' run dates in UTC, honoring the specified IANA timezone
    and handling daylight saving time (DST) shifts deterministically.
    """
    try:
        tz = zoneinfo.ZoneInfo(timezone_name)
    except Exception:
        raise ValueError(f"Zona horaria IANA desconocida o no válida: '{timezone_name}'")

    effective_cron = get_cron_expression(schedule_type, cron_expr)

    start_utc = start_from_utc or datetime.now(timezone.utc)
    # Convert start time to target timezone
    start_local = start_utc.astimezone(tz)

    itr = croniter(effective_cron, start_local)
    next_dates_utc: List[datetime] = []

    for _ in range(count):
        next_local = itr.get_next(datetime)
        # Convert local execution time back to UTC
        next_utc = next_local.astimezone(timezone.utc)
        next_dates_utc.append(next_utc)

    return next_dates_utc

def validate_target_path_template(template: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates target path template against directory traversal attacks (../) and forbidden characters.
    """
    if not template or not template.strip():
        return True, None
    t = template.strip()
    if ".." in t or t.startswith("/") or t.startswith("\\"):
        return False, "La plantilla de ruta de destino no puede contener '..' ni comenzar con '/' (riesgo de path traversal)."
    # Safe characters only
    if not re.match(r"^[a-zA-Z0-9_\-/{}\.]+$", t):
        return False, "La plantilla contiene caracteres no permitidos. Usa letras, números, '-', '_', '/', '.' y placeholders como '{source_stem}' o '{date}'."
    return True, None
