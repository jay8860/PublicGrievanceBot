"""Authentication + role-based access control for the new platform APIs.

Token format is backward compatible with ``auth.py`` (same SECRET_KEY/HMAC and
the legacy ``{"sub": username}`` payload): a token without a ``role`` claim is
treated as a dashboard admin, so existing logged-in sessions keep working.

Roles
-----
* ``superadmin`` – everything, including officer/invitation management.
* ``admin``      – department/category/TAT config, complaint oversight, reports.
* ``viewer``     – read-only dashboard access.
* ``officer``    – scoped to their department + level + jurisdiction.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import get_env

SECRET_KEY = get_env("SECRET_KEY", "super_secret_fallback_key_change_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(get_env("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_ROLES = ("superadmin", "admin")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw, hashed)
    except Exception:
        return False


def create_token(subject: str, role: str = "admin", officer_id: Optional[str] = None,
                 department_id: Optional[str] = None, level: Optional[int] = None,
                 extra: Optional[dict] = None) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if officer_id:
        payload["officer_id"] = officer_id
    if department_id:
        payload["department_id"] = department_id
    if level:
        payload["level"] = level
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})


class Principal:
    """Everything an endpoint needs to enforce department/level/jurisdiction."""

    def __init__(self, payload: dict):
        self.username: str = payload.get("sub") or "unknown"
        # Legacy tokens carry no role -> dashboard admin (pre-RBAC behaviour).
        self.role: str = payload.get("role") or "admin"
        self.officer_id: Optional[str] = payload.get("officer_id")
        self.department_id: Optional[str] = payload.get("department_id")
        self.level: Optional[int] = payload.get("level")

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"

    @property
    def is_officer(self) -> bool:
        return self.role == "officer"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Principal {self.username} role={self.role} officer={self.officer_id}>"


def get_principal(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    return Principal(decode_token(credentials.credentials))


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal


def require_superadmin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return principal


def require_officer(principal: Principal = Depends(get_principal)) -> Principal:
    if not (principal.is_officer or principal.is_admin):
        raise HTTPException(status_code=403, detail="Officer access required")
    return principal


def ensure_department_scope(principal: Principal, department_id: Optional[str]) -> None:
    """Officers may only touch their own department; admins are unrestricted."""
    if principal.is_officer and principal.department_id and department_id != principal.department_id:
        raise HTTPException(status_code=403, detail="Outside your department")
