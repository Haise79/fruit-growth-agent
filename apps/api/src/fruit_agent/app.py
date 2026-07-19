from fastapi import FastAPI

from fruit_agent.config import get_settings
from fruit_agent.identity.router import router as identity_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(identity_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
