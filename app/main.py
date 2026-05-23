import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent, compat, forecasts, health, materials, recommendations, signals, prices
from app.core.config import settings
from app.db.session import create_tables


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    # Turn down noisy loggers
    for name in ("httpx", "httpcore", "watchfiles.main", "mcp.client.streamable_http", "app.clients.hf_tgi", "app.agent.tools"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Keep high-level orchestrator logs
    for name in ("app.agent", "app.agent.orchestrator"):
        logging.getLogger(name).setLevel(logging.INFO)

_configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # app.add_event_handler("startup", create_tables)
    app.include_router(health.router)
    app.include_router(compat.router)
    app.include_router(materials.router)
    app.include_router(forecasts.router)
    app.include_router(signals.router)
    app.include_router(recommendations.router)
    app.include_router(agent.router)
    app.include_router(agent.reports_router)
    app.include_router(prices.router)
    return app


app = create_app()
