from __future__ import annotations

from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from fruit_agent.common.errors import error_content

logger = structlog.get_logger(__name__)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    request_id = _request_id.get()
    if request_id is None:
        return str(uuid4())
    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        token = _request_id.set(request_id)
        started = perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                await logger.aexception(
                    "request_failed",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                )
                response = JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content=error_content(
                        code="internal_error",
                        message="internal server error",
                        request_id=request_id,
                        details=None,
                    ),
                )
            response.headers["X-Request-ID"] = request_id
            duration_ms = round((perf_counter() - started) * 1000, 3)
            await logger.ainfo(
                "request_completed",
                request_id=request_id,
                tenant_id=getattr(request.state, "tenant_id", None),
                actor_id=getattr(request.state, "actor_id", None),
                operation=f"{request.method} {request.url.path}",
                duration_ms=duration_ms,
                outcome=(
                    "success" if response.status_code < 400 else "error"
                ),
                status_code=response.status_code,
            )
            return response
        finally:
            _request_id.reset(token)
