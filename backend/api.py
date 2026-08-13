from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException

from app.api.endpoints.auth import require_auth
from app.config import load_model_configs
from app.openai_client.model_pool import ModelPool
from app.tools.interceptors import ToolInvocation
from app.tools.registry import tool_registry

from .schemas import OptimizationRule, PreviewRequest
from .service import optimizer_service


router = APIRouter(prefix="/api/tool-optimizer", tags=["tool-optimizer"])


@router.get("/catalog")
async def get_catalog(_: bool = Depends(require_auth)):
    tools = []
    for tool in tool_registry.get_all_tools():
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.get_input_schema_for_llm(),
                "tool_type": getattr(tool, "tool_type", "direct"),
            }
        )
    configured_models = load_model_configs()
    available_names = {
        model.name for model in ModelPool(configured_models).get_available_models([])
    }
    return {
        "tools": sorted(tools, key=lambda item: item["name"]),
        "models": [
            {
                "name": model.name,
                "tags": list(model.tags),
                "available": model.name in available_names,
            }
            for model in configured_models
        ],
    }


@router.get("/rules")
async def list_rules(_: bool = Depends(require_auth)):
    return {"rules": [rule.model_dump(mode="json") for rule in optimizer_service.store.list_rules()]}


@router.post("/rules")
async def save_rule(rule: OptimizationRule, _: bool = Depends(require_auth)):
    saved = optimizer_service.store.save_rule(rule)
    return {"rule": saved.model_dump(mode="json")}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, _: bool = Depends(require_auth)):
    if not optimizer_service.store.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"status": "deleted"}


@router.post("/preview")
async def preview(request: PreviewRequest, _: bool = Depends(require_auth)):
    tool = tool_registry.get_tool(request.tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail="工具不存在")
    invocation = ToolInvocation(
        call_id="preview",
        tool_name=request.tool_name,
        raw_parameters=request.parameters,
        parameters=request.parameters,
        tool_schema=tool.get_input_schema_for_llm(),
        session_ctx=SimpleNamespace(platform="webui", session_id="tool-optimizer-preview"),
        source="preview",
        metadata={"skip_tool_interceptors": True},
    )
    try:
        result = await optimizer_service.apply_rule(invocation, request.rule)
        if result.transformations and getattr(tool, "args_schema", None):
            tool.args_schema.model_validate(result.parameters)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "raw_parameters": result.raw_parameters,
        "effective_parameters": result.parameters,
        "transformations": result.transformations,
    }


@router.get("/runs")
async def list_runs(_: bool = Depends(require_auth)):
    return {"runs": optimizer_service.list_recent_runs()}
