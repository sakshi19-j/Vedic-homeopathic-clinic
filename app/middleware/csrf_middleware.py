import hashlib
import hmac
import secrets
from typing import Callable

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        secure: bool | None = None,
        same_site: str = "lax",
        path: str = "/",
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.secure = secure if secure is not None else not settings.DEBUG
        self.same_site = same_site
        self.path = path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            return self._ensure_csrf_cookie(request, response)

        if self._has_authorization_header(request):
            return await call_next(request)

        # Only enforce CSRF for requests that carry a CSRF cookie.
        csrf_cookie_value = request.cookies.get(self.cookie_name)
        if not csrf_cookie_value:
            return await call_next(request)

        csrf_header_value = request.headers.get(self.header_name)
        if not csrf_header_value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Missing CSRF header. "
                    f"Include {self.header_name} for unsafe requests."
                ),
            )

        if not self._validate_csrf_cookie(csrf_cookie_value, csrf_header_value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired CSRF token.",
            )

        return await call_next(request)

    def _has_authorization_header(self, request: Request) -> bool:
        return bool(request.headers.get("Authorization"))

    def _ensure_csrf_cookie(self, request: Request, response: Response) -> Response:
        cookie_value = request.cookies.get(self.cookie_name)
        if cookie_value and self._parse_csrf_cookie(cookie_value) is not None:
            return response

        token = self._generate_token()
        response.set_cookie(
            self.cookie_name,
            self._serialize_csrf_token(token),
            secure=self.secure,
            httponly=False,
            samesite=self.same_site,
            path=self.path,
        )
        response.headers[self.header_name] = token
        return response

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _serialize_csrf_token(self, token: str) -> str:
        signature = hmac.new(
            settings.JWT_SECRET.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{token}:{signature}"

    def _parse_csrf_cookie(self, serialized: str) -> str | None:
        parts = serialized.split(":", 1)
        if len(parts) != 2:
            return None
        token, signature = parts
        expected = hmac.new(
            settings.JWT_SECRET.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return token if hmac.compare_digest(expected, signature) else None

    def _validate_csrf_cookie(self, cookie_value: str, header_value: str) -> bool:
        token = self._parse_csrf_cookie(cookie_value)
        return bool(token and hmac.compare_digest(token, header_value))
