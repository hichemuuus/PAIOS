"""Veyron FastAPI application entrypoint.

Wires together routes, the event bus, DB init, and (in production) serves the
built frontend. Run with:

    uvicorn veyron.main:app --reload

or via the console script: veyron
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from veyron import __version__
from veyron.config import get_settings
from veyron.core.events import get_bus
from veyron.db.base import init_db
from veyron.security.confirmations import get_manager

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Rotating-file + stderr logging."""
    from logging.handlers import RotatingFileHandler

    from veyron.config import DATA_DIR

    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler(log_dir / "veyron.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    _configure_logging()
    init_db()
    # Force eager init of singletons so errors surface at startup, not mid-request.
    get_bus()
    get_manager()
    # Touch the registry so tool discovery happens once now.
    from veyron.tools.registry import get_registry
    names = get_registry().names()
    logger.info("Veyron %s started; %d tools registered: %s", __version__, len(names), names)
    # Enhanced LLM provider diagnostics.
    try:
        from veyron.llm.base import get_provider

        cfg = get_settings()
        provider = get_provider()
        has_remote = bool(cfg.model.remote_enabled and cfg.model.remote_url and cfg.model.remote_api_key)

        import time

        import httpx

        primary_available = False
        primary_latency = 0.0
        primary_model_found = False
        try:
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{cfg.model.ollama_url}/api/tags")
                primary_latency = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
                    primary_available = True
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    primary_model_found = any(cfg.model.base_model in m for m in models)
                    logger.info(
                        "Ollama: %s | model '%s' %s | %d models | %.0fms",
                        "available" if primary_available else "unreachable",
                        cfg.model.base_model,
                        "found" if primary_model_found else "not found (run: ollama pull %s)" % cfg.model.base_model,
                        len(models),
                        primary_latency,
                    )
                else:
                    logger.warning("Ollama returned HTTP %d", resp.status_code)
        except httpx.ConnectError:
            logger.warning("Ollama not reachable at %s (is the server running?)", cfg.model.ollama_url)
        except Exception as e:
            logger.warning("Ollama check failed: %s", e)

        if has_remote:
            remote_available = False
            try:
                start = time.monotonic()
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{cfg.model.remote_url}/models",
                        headers={"Authorization": f"Bearer {cfg.model.remote_api_key}"},
                    )
                    remote_latency = (time.monotonic() - start) * 1000
                    remote_available = resp.status_code == 200
                    logger.info(
                        "Remote: %s at %s (%s) | %.0fms",
                        "available" if remote_available else "unreachable",
                        cfg.model.remote_url,
                        cfg.model.remote_model,
                        remote_latency,
                    )
            except Exception as e:
                logger.warning("Remote provider check failed: %s", e)
        else:
            logger.info("Remote fallback: not configured (set model.remote_enabled=true to enable)")

        if not primary_available and not has_remote:
            logger.warning(
                "No LLM provider available. Install Ollama (https://ollama.ai) and "
                "pull a model: ollama pull %s", cfg.model.base_model,
            )

        # Log micro-model status.
        if cfg.model.micro_models_enabled:
            logger.info(
                "Micro-models enabled (threshold=%.2f): intelligence layer active",
                cfg.model.micro_model_confidence_threshold,
            )
        else:
            logger.info("Micro-models disabled (set model.micro_models_enabled=true to enable)")
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM diagnostics failed: %s", e)

    # Start the intelligence scheduler for background retraining.
    from veyron.intelligence.scheduler import IntelligenceScheduler
    settings = get_settings()
    scheduler = IntelligenceScheduler(
        interval_seconds=settings.model.scheduler_interval_seconds,
        retrain_min_growth_pct=settings.model.retrain_min_growth_pct,
    )
    app.state.scheduler = scheduler
    await scheduler.start()

    yield

    # Shutdown cleanup.
    await scheduler.stop()
    bus = get_bus()
    await bus.shutdown()
    logger.info("Veyron shutdown complete")


def create_app() -> FastAPI:
    """Build the FastAPI app. Used by uvicorn and tests."""
    settings = get_settings()
    app = FastAPI(
        title="Veyron",
        description="Veyron AI — productivity agent API",
        version=__version__,
        lifespan=lifespan,
    )

    # Middleware: rate limiting, request IDs.
    from veyron.api.middleware import RateLimitMiddleware, RequestIDMiddleware

    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)
    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes.
    from veyron.api.routes import agent, dashboard, intelligence, memory, projects, system, tools
    from veyron.api.websocket import router as ws_router

    app.include_router(agent.router)
    app.include_router(system.router)
    app.include_router(tools.router)
    app.include_router(projects.router)
    app.include_router(memory.router)
    app.include_router(dashboard.router)
    app.include_router(intelligence.router)
    app.include_router(ws_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "environment": settings.environment}

    @app.get("/api/info")
    async def info() -> dict:
        from veyron.llm.base import get_provider
        from veyron.tools.registry import get_registry

        provider = get_provider()
        cfg = get_settings()
        return {
            "version": __version__,
            "tools": get_registry().names(),
            "sandbox_roots": settings.security.sandbox_roots,
            "model": {
                "base_model": cfg.model.base_model,
                "ollama_url": cfg.model.ollama_url,
                "provider": provider.name,
                "remote_enabled": cfg.model.remote_enabled,
                "remote_url": cfg.model.remote_url or None,
                "remote_model": cfg.model.remote_model if cfg.model.remote_enabled else None,
            },
        }

    # Serve the built frontend in production mode if it exists.
    dist = Path(settings.server.frontend_dist)
    if settings.environment == "prod" and dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:
        @app.get("/")
        async def root() -> dict:
            return {
                "name": "Veyron",
                "version": __version__,
                "message": "Veyron API is running.",
                "endpoints": {
                    "dashboard": "/api/dashboard",
                    "agents": "/api/agent",
                    "system": "/api/system",
                    "tools": "/api/tools",
                    "projects": "/api/projects",
                    "memory": "/api/memory",
                    "intelligence": "/api/intelligence/metrics",
                },
                "docs": "/docs",
                "websocket": "/ws",
            }

    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "veyron.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.environment == "dev",
    )


if __name__ == "__main__":
    run()
