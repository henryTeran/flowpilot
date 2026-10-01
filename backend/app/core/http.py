import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from app.core.config import settings
from app.core.errors import build_error_response
from app.core.logging_config import configure_logging, reset_request_id, set_request_id
from app.core.rate_limit import InMemoryRateLimiter, request_client_fingerprint


logger = logging.getLogger(__name__)
auth_rate_limiter = InMemoryRateLimiter()


def _apply_security_headers(response) -> None:
    if settings.ENABLE_SECURITY_HEADERS:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")


def _is_auth_login_request(request: Request) -> bool:
    return request.method.upper() == "POST" and request.url.path == f"{settings.API_V1_PREFIX}/auth/login"


def _auth_rate_limit_reached(request: Request) -> bool:
    if not settings.ENABLE_RATE_LIMITING:
        return False
    if not _is_auth_login_request(request):
        return False

    fingerprint = request_client_fingerprint(
        request.headers.get("X-Forwarded-For"),
        request.client.host if request.client else None,
    )
    key = f"auth-login:{fingerprint}"
    return auth_rate_limiter.is_limited(
        key=key,
        max_requests=settings.RATE_LIMIT_AUTH_MAX_REQUESTS,
        window_seconds=settings.RATE_LIMIT_AUTH_WINDOW_SECONDS,
    )


def configure_http_middleware(app: FastAPI) -> None:
    configure_logging()

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)
        started_at = perf_counter()
        status_code = 500
        try:
            if _auth_rate_limit_reached(request):
                status_code = 429
                response = build_error_response(
                    request=request,
                    status_code=429,
                    code="rate_limit_exceeded",
                    message="Trop de tentatives de connexion. Reessayez dans quelques instants.",
                )
                response.headers["X-Request-ID"] = request_id
                _apply_security_headers(response)
                return response

            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            _apply_security_headers(response)

            return response
        except Exception as exc:
            # Keep exception values and request data out of application logs.
            logger.error("Unhandled application error", extra={"error_type": type(exc).__name__})
            raise
        finally:
            route = request.scope.get("route")
            logger.info("HTTP request completed", extra={
                "request_id": request_id,
                "method": request.method,
                "path": getattr(route, "path", None) or "<unmatched>",
                "status_code": status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            })
            reset_request_id(token)
