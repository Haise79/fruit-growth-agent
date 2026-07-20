from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fruit_agent.approvals.router import router as approvals_router
from fruit_agent.audit.middleware import RequestContextMiddleware
from fruit_agent.audit.middleware import get_request_id
from fruit_agent.common.errors import DomainError, error_content
from fruit_agent.common.redaction import redact
from fruit_agent.config import get_settings
from fruit_agent.copilot.router import router as copilot_router
from fruit_agent.identity.router import router as identity_router
from fruit_agent.imports.router import router as imports_router
from fruit_agent.knowledge.router import router as knowledge_router
from fruit_agent.logging import configure_logging
from fruit_agent.model_gateway.router import router as model_gateway_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestContextMiddleware)
    app.include_router(approvals_router)
    app.include_router(identity_router)
    app.include_router(imports_router)
    app.include_router(knowledge_router)
    app.include_router(model_gateway_router)
    app.include_router(copilot_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        return JSONResponse(
            status_code=422,
            content=error_content(
                code="validation_error",
                message="request validation failed",
                request_id=request_id,
                details=jsonable_encoder(redact(exc.errors())),
            ),
        )

    @app.exception_handler(DomainError)
    async def domain_error(
        request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        return JSONResponse(
            status_code=exc.status_code,
            content=error_content(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                details=jsonable_encoder(redact(exc.details)),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_error(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", get_request_id())
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_content(
                code=f"http_{exc.status_code}",
                message=(
                    exc.detail
                    if isinstance(exc.detail, str)
                    else "request failed"
                ),
                request_id=request_id,
                details=jsonable_encoder(redact(exc.detail)),
            ),
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
