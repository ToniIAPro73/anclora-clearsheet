import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models import get_db, User, AuthWhitelist, AuthAuditEvent

# JWT Configuration. Production must provide a secret; local development and tests use
# a process-local random fallback so no reusable credential is embedded in source.
APP_ENV = os.environ.get("APP_ENV", "development").lower()
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET is required when APP_ENV=production")
    JWT_SECRET = secrets.token_urlsafe(32)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Operational Whitelist and Security Settings
def get_admin_emails() -> List[str]:
    raw = os.environ.get("AUTH_ADMIN_EMAILS", "")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]

AUTH_WHITELIST_TOKEN_TTL_HOURS = int(os.environ.get("AUTH_WHITELIST_TOKEN_TTL_HOURS", "72"))
AUTH_PASSWORD_MIN_LENGTH = int(os.environ.get("AUTH_PASSWORD_MIN_LENGTH", "12"))

ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16
)

security_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)

def record_audit_event(
    db: Session,
    event: str,
    email: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditEvent:
    audit_entry = AuthAuditEvent(
        event=event,
        email=email.strip().lower() if email else None,
        user_id=user_id,
        metadata_json=metadata or {}
    )
    db.add(audit_entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return audit_entry

def create_access_token(user_id: str, email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_optional(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[User]:
    # Check HttpOnly cookie first, then Bearer header
    token = request.cookies.get("access_token")
    if not token and auth:
        token = auth.credentials

    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.status != "active":
            return None

        # Verify active whitelist admission
        whitelist = db.query(AuthWhitelist).filter(
            (AuthWhitelist.user_id == user.id) | (AuthWhitelist.email == user.email.lower())
        ).first()
        if not whitelist or whitelist.status != "active":
            return None

        return user
    except Exception:
        return None

def get_current_user_required(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticación requerida para esta acción.")
    return current_user

def get_current_admin_user(
    current_user: User = Depends(get_current_user_required)
) -> User:
    admin_emails = get_admin_emails()
    if not admin_emails or current_user.email.strip().lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores.")
    return current_user

