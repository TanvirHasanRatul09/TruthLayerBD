import hashlib
import hmac
import secrets

from fastapi import Request

from app.core.config import get_settings

COOKIE_NAME = "truthlayer_visitor"


def _signature(token: str) -> str:
    return hmac.new(get_settings().app_secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def visitor_id(request: Request) -> str:
    return request.state.visitor_id


async def visitor_session_middleware(request: Request, call_next):
    cookie = request.cookies.get(COOKIE_NAME, "")
    token, separator, signature = cookie.partition(".")
    valid = bool(separator and len(token) >= 32 and len(token) <= 128 and hmac.compare_digest(_signature(token), signature))
    if not valid:
        token = secrets.token_urlsafe(32)
    request.state.visitor_id = hashlib.sha256(token.encode()).hexdigest()
    response = await call_next(request)
    if not valid:
        response.set_cookie(
            COOKIE_NAME, f"{token}.{_signature(token)}", httponly=True,
            secure=get_settings().app_env == "production", samesite="lax",
            max_age=60 * 60 * 24 * 365, path="/",
        )
    return response
