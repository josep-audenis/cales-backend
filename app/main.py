from fastapi import FastAPI

from app.api.routes import agent, forecasts, health, materials, recommendations, signals, prices
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health.router)
    app.include_router(materials.router)
    app.include_router(forecasts.router)
    app.include_router(signals.router)
    app.include_router(recommendations.router)
    app.include_router(agent.router)
    app.include_router(prices.router)
    return app


app = create_app()
