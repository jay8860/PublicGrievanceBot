from datetime import datetime, timedelta
from typing import Optional
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from config import get_env

logger = logging.getLogger(__name__)

# CONFIG
_DEFAULT_SECRET_KEY = "super_secret_fallback_key_change_in_prod"
_DEFAULT_ADMIN_PASSWORD = "admin123"

SECRET_KEY = get_env("SECRET_KEY", _DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 Hours

ADMIN_USERNAME = get_env("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = get_env("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)

if SECRET_KEY == _DEFAULT_SECRET_KEY:
    logger.warning(
        "SECURITY WARNING: SECRET_KEY env var is not set. Using an insecure "
        "default. Set SECRET_KEY before deploying to production."
    )
if ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD:
    logger.warning(
        "SECURITY WARNING: ADMIN_PASSWORD is the insecure default "
        "('admin123'). Set a strong ADMIN_USERNAME/ADMIN_PASSWORD before "
        "deploying to production."
    )

# --- TEMPORARY LOGIN BYPASS (hide the login screen "for now") -------------
# Set BYPASS_LOGIN=true (env var or .env) to hide the dashboard login for the
# time being. NOTHING is removed: the Login screen, the password check, the
# JWT issuing/verification and the token expiry all stay exactly as they are.
# This flag only lets the protected routes accept a request WITHOUT a token,
# so the dashboard opens directly.
# To bring the login back: set BYPASS_LOGIN=false (or delete the variable)
# and restart the API - no other change needed.
BYPASS_LOGIN = get_env("BYPASS_LOGIN", "false").lower() in ("1", "true", "yes", "on")

# Username reported for requests that came in while the bypass is on.
BYPASS_LOGIN_USER = "bypass-login"

if BYPASS_LOGIN:
    logger.warning(
        "SECURITY WARNING: BYPASS_LOGIN is enabled - the dashboard is "
        "reachable WITHOUT a login. This is a temporary dev/emergency switch; "
        "set BYPASS_LOGIN=false and restart the API before any public "
        "deployment."
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
    # TEMPORARY: while BYPASS_LOGIN is on, every request counts as an
    # authenticated admin, so the dashboard works without a token. Turn the
    # bypass off to restore the normal JWT check below, unchanged.
    if BYPASS_LOGIN:
        return BYPASS_LOGIN_USER

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
