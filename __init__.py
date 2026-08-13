from __future__ import annotations

from app.logger import setup_logger
from app.tools.interceptors import tool_interceptor_registry

from .backend.api import router
from .backend.service import optimizer_service


logger = setup_logger(__name__)
INTERCEPTOR_NAME = "optimize_selected_arguments"


async def _before_tool_execute(invocation):
    return await optimizer_service.optimize(invocation)


async def startup() -> None:
    optimizer_service.store.ensure_storage()
    logger.info("Tool optimizer plugin started")


async def enable() -> None:
    tool_interceptor_registry.register(
        owner=__name__,
        name=INTERCEPTOR_NAME,
        callback=_before_tool_execute,
        priority=100,
        timeout_ms=300_000,
        failure_policy="fail_call",
    )
    logger.info("Tool optimizer plugin enabled")


async def disable() -> None:
    tool_interceptor_registry.unregister(owner=__name__, name=INTERCEPTOR_NAME)
    logger.info("Tool optimizer plugin disabled")


async def shutdown() -> None:
    await disable()
    logger.info("Tool optimizer plugin stopped")


__all__ = ["router", "startup", "enable", "disable", "shutdown"]
