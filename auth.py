from datetime import datetime, timedelta
from typing import Optional
import logging
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# CONFIG
_DEFAULT_SECRET_KEY = "super_secret_fallback_key_change_in_prod"
_DEFAULT_ADMIN_PASSWORD = "admin123"

SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 Hours

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)

if SECRET_KEY == _DEFAULT_SECRET_KEY:
    logger.warning(
        "SECURITY WARNING: SECRET_KEY env var is not set. Using an insecure "
        "default. Set SECRET_KEY before deploying to production."
    )
if ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD:
    logger.warning(
        "SECURITY WARNING: ADMIN_PASSWORD env var is not set. Using an "
        "insecure default ('admin123'). Set ADMIN_USERNAME/ADMIN_PASSWORD "
        "before deploying to production."
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_admin(username, password):
    """Simple check against env vars."""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return True
    return False


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency: validates the Bearer JWT and returns the username.

    Raise 401 for any missing/invalid/expired token so protected routes
    can simply declare `Depends(get_current_admin)`.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise unauthorized

    username = payload.get("sub")
    if not username:
        raise unauthorized

    return username
