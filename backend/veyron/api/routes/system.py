"""System API routes.

  GET /api/system/overview    — snapshot of CPU/RAM/disk
  GET /api/system/cpu
  GET /api/system/memory
  GET /api/system/disk
  GET /api/system/health
  GET /api/system/processes   — top-N processes by cpu or memory
  GET /api/system/provider    — LLM provider diagnostics
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from veyron.tools.base import ToolContext
from veyron.tools.system_monitor import SystemMonitorTool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

_tool = SystemMonitorTool()


async def _run(op: str, **kwargs) -> dict:
    ctx = ToolContext(task_public_id="system")
    result = await _tool.run(ctx, operation=op, **kwargs)
    return {"ok": result.ok, "output": result.output, "data": result.data, "error": result.error}


@router.get("/overview")
async def overview() -> dict:
    return await _run("overview")


@router.get("/cpu")
async def cpu() -> dict:
    return await _run("cpu")


@router.get("/memory")
async def memory() -> dict:
    return await _run("memory")


@router.get("/disk")
async def disk() -> dict:
    return await _run("disk")


@router.get("/health")
async def health() -> dict:
    return await _run("health")


@router.get("/processes")
async def processes(
    count: int = Query(default=12, ge=1, le=100),
    sort_by: str = Query(default="cpu", pattern="^(cpu|memory)$"),
) -> dict:
    """Top-N processes by cpu or memory usage."""
    return await _run("processes", process_count=count, sort_processes_by=sort_by)


@router.get("/provider")
async def provider_diagnostics() -> dict:
    """LLM provider health and configuration diagnostics.

    Tests connectivity to the configured local and remote providers
    and reports their status, latency, and available models.
    """
    from veyron.config import get_settings
    from veyron.llm.base import get_provider

    cfg = get_settings()
    provider = get_provider()

    primary_name = "ollama"
    primary_available = False
    primary_latency_ms = 0.0
    primary_models: list[str] = []

    try:
        import time

        import httpx
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{cfg.model.ollama_url}/api/tags")
            if resp.status_code == 200:
                primary_available = True
                primary_models = [m.get("name", "") for m in resp.json().get("models", [])]
            primary_latency_ms = round((time.monotonic() - start) * 1000, 1)
    except Exception as e:
        logger.debug("ollama diagnostics: %s", e)

    remote_available = False
    remote_latency_ms = 0.0
    remote_configured = bool(cfg.model.remote_enabled and cfg.model.remote_url and cfg.model.remote_api_key)
    if remote_configured:
        try:
            import time

            import httpx
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{cfg.model.remote_url}/models",
                    headers={"Authorization": f"Bearer {cfg.model.remote_api_key}"},
                )
                remote_available = resp.status_code == 200
                remote_latency_ms = round((time.monotonic() - start) * 1000, 1)
        except Exception as e:
            logger.debug("remote diagnostics: %s", e)

    return {
        "provider_chain": provider.name,
        "primary": {
            "name": primary_name,
            "url": cfg.model.ollama_url,
            "model": cfg.model.base_model,
            "available": primary_available,
            "latency_ms": primary_latency_ms,
            "models_available": primary_models,
        },
        "remote": {
            "configured": remote_configured,
            "url": cfg.model.remote_url or None,
            "model": cfg.model.remote_model if remote_configured else None,
            "available": remote_available,
            "latency_ms": remote_latency_ms if remote_configured else None,
        },
        "micro_models": {
            "enabled": cfg.model.micro_models_enabled,
            "confidence_threshold": cfg.model.micro_model_confidence_threshold,
        },
        "fallback_available": remote_configured,
    }
