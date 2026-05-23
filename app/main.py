from fastapi import FastAPI

from app.api.routes import forecasts, health, materials, recommendations, signals
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health.router)
    app.include_router(materials.router)
    app.include_router(forecasts.router)
    app.include_router(signals.router)
    app.include_router(recommendations.router)
    return app


app = create_app()
