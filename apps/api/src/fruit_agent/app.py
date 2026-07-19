from fastapi import FastAPI

from fruit_agent.approvals.router import router as approvals_router
from fruit_agent.audit.middleware import RequestContextMiddleware
from fruit_agent.config import get_settings
from fruit_agent.identity.router import router as identity_router
from fruit_agent.knowledge.router import router as knowledge_router
from fruit_agent.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestContextMiddleware)
    app.include_router(approvals_router)
    app.include_router(identity_router)
    app.include_router(knowledge_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
