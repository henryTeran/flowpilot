import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

from app.core.config import settings
from app.core.logging_config import configure_logging, reset_request_id, set_request_id


logger = logging.getLogger(__name__)


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
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id

            if settings.ENABLE_SECURITY_HEADERS:
                response.headers.setdefault("X-Content-Type-Options", "nosniff")
                response.headers.setdefault("X-Frame-Options", "DENY")
                response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

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
