import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_state import get_auth_state
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    verify_password,
)
from app.database.connection import get_db
from app.database.models.user import User

router = APIRouter()

# Security-event audit log. INFO records who did what and from where; it
# must never carry passwords, tokens or API keys (enforced by construction:
# only identifiers, outcomes and IP addresses are logged).
audit_log = logging.getLogger("schedulai.audit")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_COOKIE_ACCESS = "access_token"
_COOKIE_REFRESH = "refresh_token"


def _throttle_key(ip: str, account: str) -> str:
    return f"{ip}|{account.lower().strip()}"


def _client_ip(request: Request) -> str:
    """Best-effort client IP for throttling and audit logs.

    Behind the production Nginx proxy every connection arrives from a
    private proxy address, so the last X-Forwarded-For entry (appended by
    our proxy) identifies the client. Direct connections from public
    addresses ignore X-Forwarded-For entirely, since it is client-controlled
    there and trusting it would let attackers rotate identities past the
    throttle. Returns "unknown" only when nothing usable is present.
    """
    peer = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and peer and _is_private_ip(peer):
        candidates = [part.strip() for part in forwarded.split(",") if part.strip()]
        if candidates:
            return candidates[-1]
    return peer or "unknown"


def _is_private_ip(host: str) -> bool:
    import ipaddress

    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


async def _check_login_throttle(request: Request, account: str) -> None:
    allowed = await get_auth_state().check_login_allowed(
        _throttle_key(_client_ip(request), account)
    )
    if not allowed:
        audit_log.warning(
            "auth.login.throttled account=%s ip=%s", account.lower().strip(), _client_ip(request)
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again shortly.",
        )


async def _clear_login_throttle(request: Request, account: str) -> None:
    await get_auth_state().clear_login(_throttle_key(_client_ip(request), account))


def _token_ttl_seconds(payload: dict, default: int) -> int:
    try:
        return max(1, int(payload.get("exp", 0)) - int(time.time()))
    except (TypeError, ValueError):
        return default


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)


def _resolve_access_token(
    request: Request,
    oauth_token: str | None = None,
) -> str | None:
    if oauth_token:
        return oauth_token
    bearer = _extract_bearer_token(request.headers.get("authorization"))
    if bearer:
        return bearer
    cookie = request.cookies.get(_COOKIE_ACCESS)
    return cookie or None


async def _assert_not_revoked(payload: dict) -> None:
    if await get_auth_state().is_jti_revoked(payload.get("jti", "")):
        raise UnauthorizedError("Token has been revoked")


async def _get_local_user(db: AsyncSession) -> User:
    """Resolve the existing local actor without creating database records."""
    from sqlalchemy.orm import selectinload

    query = select(User).options(selectinload(User.roles)).where(User.is_active.is_(True))
    if settings.LOCAL_AUTH_USER_EMAIL:
        query = query.where(User.email == settings.LOCAL_AUTH_USER_EMAIL)
    else:
        query = query.order_by(User.created_at)

    try:
        user = (await db.execute(query)).scalars().first()
    except SQLAlchemyError as exc:
        audit_log.warning("auth.local_bypass.unavailable reason=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local auth bypass requires migrated application tables",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local auth bypass requires an existing active users row; no record was created",
        )
    return user


async def get_current_user(
    request: Request,
    oauth_token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if settings.LOCAL_AUTH_DISABLED:
        return await _get_local_user(db)

    token = _resolve_access_token(request, oauth_token)
    if not token:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(token, expected_type="access")
        user_id = UUID(payload["sub"])
    except Exception:
        raise UnauthorizedError() from None
    await _assert_not_revoked(payload)

    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError()
    return user


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    # HttpOnly cookies. SameSite=Lax allows top-level login navigation;
    # Secure is enabled in production (HTTPS). Frontend keeps Bearer fallback.
    # TTLs derive from settings so cookie expiry never drifts from JWT expiry.
    from app.core.config import settings as _settings
    from app.core.security import REFRESH_TOKEN_EXPIRE_DAYS

    secure = False
    try:
        secure = _settings.APP_ENV == "production"
    except Exception:
        secure = False
    response.set_cookie(
        _COOKIE_ACCESS,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int(_settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
    )
    response.set_cookie(
        _COOKIE_REFRESH,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=int(REFRESH_TOKEN_EXPIRE_DAYS) * 24 * 3600,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(_COOKIE_ACCESS, path="/")
    response.delete_cookie(_COOKIE_REFRESH, path="/api/v1/auth")


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    await _check_login_throttle(request, form_data.username)
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        audit_log.warning(
            "auth.login.failure account=%s ip=%s reason=bad_credentials",
            form_data.username.lower().strip(),
            _client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Checked after the password so a disabled account is only revealed to its owner.
    if not user.is_active:
        audit_log.warning(
            "auth.login.failure account=%s ip=%s reason=account_disabled",
            form_data.username.lower().strip(),
            _client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    await _clear_login_throttle(request, form_data.username)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    _set_auth_cookies(response, access_token, refresh_token)
    audit_log.info(
        "auth.login.success account=%s user_id=%s ip=%s",
        user.email,
        user.id,
        _client_ip(request),
    )
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
):
    raw = (
        (body.refresh_token if body and body.refresh_token else None)
        or request.cookies.get(_COOKIE_REFRESH)
        or _extract_bearer_token(request.headers.get("authorization"))
    )
    if not raw:
        raise UnauthorizedError("Refresh token required")
    try:
        payload = decode_access_token(raw, expected_type="refresh")
        user_id = str(UUID(payload["sub"]))
    except Exception:
        raise UnauthorizedError() from None
    await _assert_not_revoked(payload)
    # Rotation: single-use refresh tokens. Revoke the presenting jti for its
    # remaining lifetime so a stolen copy dies with first use.
    await get_auth_state().revoke_jti(
        payload.get("jti", ""), _token_ttl_seconds(payload, default=7 * 24 * 3600)
    )
    new_access = create_access_token(data={"sub": user_id})
    new_refresh = create_refresh_token(data={"sub": user_id})
    _set_auth_cookies(response, new_access, new_refresh)
    audit_log.info("auth.refresh.rotated user_id=%s ip=%s", user_id, _client_ip(request))
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    revoked_user: str | None = None
    # Collect distinct presented tokens (header bearer + both cookies). The
    # previous loop preferred the bearer over cookies on every iteration, so
    # when access and refresh arrived via different channels only one was
    # revoked. Revoke every distinct token as whichever type it decodes to.
    candidates: list[str] = []
    bearer = _extract_bearer_token(request.headers.get("authorization"))
    if bearer:
        candidates.append(bearer)
    for cookie_name in (_COOKIE_ACCESS, _COOKIE_REFRESH):
        cookie_raw = request.cookies.get(cookie_name)
        if cookie_raw and cookie_raw not in candidates:
            candidates.append(cookie_raw)
    for raw in candidates:
        for expected in ("access", "refresh"):
            try:
                payload = decode_access_token(raw, expected_type=expected)
            except Exception:
                continue
            await get_auth_state().revoke_jti(
                payload.get("jti", ""), _token_ttl_seconds(payload, default=1800)
            )
            revoked_user = revoked_user or str(payload.get("sub"))
            break
    _clear_auth_cookies(out)
    audit_log.info("auth.logout user_id=%s ip=%s", revoked_user or "unknown", _client_ip(request))
    return out


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    roles = [role.name for role in current_user.roles]
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        roles=roles,
    )
