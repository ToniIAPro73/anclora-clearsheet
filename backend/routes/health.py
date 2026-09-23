from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from models import check_database

router = APIRouter(tags=["health"])

@router.get("/status")
def status_check():
    return {
        "status": "healthy",
        "service": "Anclora CleanSheet API",
        "time": datetime.now(timezone.utc).isoformat(),
        "database": "PostgreSQL / SQLAlchemy (Alembic ready)"
    }

@router.get("/health")
def health_check():
    try:
        check_database()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {
        "status": "healthy",
        "service": "Anclora CleanSheet API",
        "database": "ok",
    }
