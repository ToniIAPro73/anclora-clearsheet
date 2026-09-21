from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from models import get_db, Execution, User
from auth import get_current_user_required

router = APIRouter(prefix="/executions", tags=["executions"])

@router.get("")
def list_executions(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    executions = db.query(Execution).filter(Execution.user_id == user.id).order_by(Execution.created_at.desc()).all()
    return executions
