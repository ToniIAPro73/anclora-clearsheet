from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/status")
def status_check():
    return {
        "status": "healthy",
        "service": "Anclora CleanSheet API",
        "time": datetime.now(timezone.utc).isoformat(),
        "database": "PostgreSQL / SQLAlchemy (Alembic ready)"
    }
