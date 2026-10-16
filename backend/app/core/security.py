from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
from jose import jwt

from app.core.config import settings

# bcrypt only uses the first 72 bytes. bcrypt>=5 raises on longer input instead of
# truncating, so truncate explicitly (same result as the old passlib behaviour).
_BCRYPT_MAX_BYTES = 72


def validate_password_strength(password: str) -> None:
    """Enforce the configurable password policy at user-creation boundaries.

    Raises ValueError with a user-safe message. The hash function itself
    stays unopinionated so existing stored hashes keep verifying.
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed stored hash: treat as a failed login rather than a 500.
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "iss": settings.APP_NAME,
            "jti": uuid4().hex,
            "type": "access",
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return str(encoded_jwt)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    delta = expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(UTC) + delta
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.now(UTC),
            "iss": settings.APP_NAME,
            "jti": uuid4().hex,
            "type": "refresh",
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return str(encoded_jwt)


def decode_access_token(token: str, expected_type: str = "access") -> dict:
    """Validate signature, expiry and token type (pure function, no I/O).

    Revocation is checked separately by async request paths via
    app.core.auth_state, so this stays usable without a running loop.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    data = dict(payload)
    if data.get("type", "access") != expected_type:
        # Tokens issued before the type claim default to access for backwards compat.
        if not (expected_type == "access" and "type" not in payload):
            raise jwt.JWTError(f"Unexpected token type: {data.get('type')}")
    return data
