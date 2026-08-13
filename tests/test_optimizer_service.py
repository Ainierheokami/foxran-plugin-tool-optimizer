from __future__ import annotations

from types import SimpleNamespace
import sys
from typing import Literal

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from app.tools.interceptors import ToolInvocation
from app.tools.interceptors import tool_interceptor_registry
from foxran_tool_optimizer_test.backend.schemas import OptimizationRule
from foxran_tool_optimizer_test.backend.schemas import PreviewRequest
from foxran_tool_optimizer_test.backend.service import ToolOptimizerService
from foxran_tool_optimizer_test.backend.store import RuleStore
from foxran_tool_optimizer_test.backend.api import _validate_preview_parameters


def make_rule(**overrides):
    payload = {
        "id": "image-prompt",
        "name": "Image prompt",
        "match": {"tools": ["image_generation"], "sources": ["agent_ast"]},
        "targets": [{"path": "prompt", "mode": "rewrite"}],
        "optimizer": {
            "model_selector": {"models": ["optimizer-model"], "fallback_tags": ["fast"]},
            "system_prompt": "Keep the subject unchanged.",
            "instruction_template": "Improve the visual prompt.",
        },
    }
    payload.update(overrides)
    return OptimizationRule.model_validate(payload)


def make_invocation(prompt="draw a fox"):
    return ToolInvocation(
        call_id="call-1",
        tool_name="image_generation",
        raw_parameters={"prompt": prompt, "width": 1024},
        parameters={"prompt": prompt, "width": 1024},
        tool_schema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}, "width": {"type": "integer"}},
        },
        session_ctx=SimpleNamespace(platform="webui", session_id="test"),
        source="agent_ast",
    )


def test_rule_store_round_trip(tmp_path):
    store = RuleStore(tmp_path)
    store.save_rule(make_rule())

    loaded = store.list_rules()

    assert [rule.id for rule in loaded] == ["image-prompt"]
    assert store.delete_rule("image-prompt") is True
    assert store.list_rules() == []


def test_preview_rejects_invalid_tool_parameters_before_model_call():
    class VideoArgs(BaseModel):
        prompt: str
        duration: int = 5
        format: Literal["mp4", "gif"] = "mp4"

    tool = SimpleNamespace(args_schema=VideoArgs)

    with pytest.raises(HTTPException) as captured:
        _validate_preview_parameters(
            tool,
            {"prompt": "generate a video", "duration": None, "format": "example"},
        )

    assert captured.value.status_code == 422
    assert "duration" in captured.value.detail
    assert "format" in captured.value.detail


def test_preview_accepts_omitted_optional_parameters_with_schema_defaults():
    class VideoArgs(BaseModel):
        prompt: str
        duration: int = 5
        format: Literal["mp4", "gif"] = "mp4"

    _validate_preview_parameters(
        SimpleNamespace(args_schema=VideoArgs),
        {"prompt": "generate a video"},
    )


@pytest.mark.asyncio
async def test_preview_optimizes_parameters_without_executing_target_tool(monkeypatch):
    from foxran_tool_optimizer_test.backend import api as api_module

    class PreviewArgs(BaseModel):
        prompt: str

    class PreviewOnlyTool:
        args_schema = PreviewArgs

        @staticmethod
        def get_input_schema_for_llm():
            return PreviewArgs.model_json_schema()

        async def execute(self, **_kwargs):
            raise AssertionError("preview must not execute the target tool")

    async def fake_apply_rule(invocation, _rule):
        invocation.parameters = {"prompt": "optimized prompt"}
        invocation.transformations.append({"paths": ["prompt"]})
        return invocation

    monkeypatch.setattr(api_module.tool_registry, "get_tool", lambda _name: PreviewOnlyTool())
    monkeypatch.setattr(api_module.optimizer_service, "apply_rule", fake_apply_rule)

    response = await api_module.preview(
        PreviewRequest(
            rule=make_rule(),
            tool_name="image_generation",
            parameters={"prompt": "original prompt"},
        ),
        True,
    )

    assert response["raw_parameters"] == {"prompt": "original prompt"}
    assert response["effective_parameters"] == {"prompt": "optimized prompt"}


@pytest.mark.asyncio
async def test_apply_rule_only_updates_selected_path(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    captured = {}

    async def fake_ask_model(*, messages, model_names, tags, usage, **_kwargs):
        captured.update({"messages": messages, "model_names": model_names, "tags": tags})
        usage["model_name"] = "optimizer-model"
        return '{"updates":{"prompt":"draw a cinematic red fox"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))

    result = await service.apply_rule(make_invocation(), make_rule())

    assert result.raw_parameters == {"prompt": "draw a fox", "width": 1024}
    assert result.parameters == {"prompt": "draw a cinematic red fox", "width": 1024}
    assert result.transformations[0]["paths"] == ["prompt"]
    assert captured["model_names"] == ["optimizer-model"]
    assert captured["tags"] == ["fast"]


@pytest.mark.asyncio
async def test_optimize_fail_open_uses_original_parameters(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(**_kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    store = RuleStore(tmp_path)
    store.save_rule(make_rule())
    service = ToolOptimizerService(store)

    result = await service.optimize(make_invocation())

    assert result.parameters == {"prompt": "draw a fox", "width": 1024}
    assert result.transformations == []
    assert service.list_recent_runs()[0]["success"] is False


@pytest.mark.asyncio
async def test_guardrail_rejects_removed_url(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(**_kwargs):
        return '{"updates":{"prompt":"describe the reference image"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    invocation = make_invocation("describe https://example.test/reference.png")

    with pytest.raises(ValueError, match="removed URLs"):
        await service.apply_rule(invocation, make_rule())


@pytest.mark.asyncio
async def test_non_prompt_field_requires_advanced_mode(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(**_kwargs):
        return '{"updates":{"width":2048}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(targets=[{"path": "width", "mode": "rewrite"}])

    with pytest.raises(ValueError, match="not prompt-like"):
        await service.apply_rule(make_invocation(), rule)


@pytest.mark.asyncio
async def test_plugin_enable_and_disable_manage_interceptor_registration():
    plugin = sys.modules["foxran_tool_optimizer_test"]

    await plugin.enable()
    try:
        assert any(
            item.owner == "foxran_tool_optimizer_test"
            for item in tool_interceptor_registry.list_registrations()
        )
    finally:
        await plugin.disable()

    assert not any(
        item.owner == "foxran_tool_optimizer_test"
        for item in tool_interceptor_registry.list_registrations()
    )


@pytest.mark.asyncio
async def test_corrupt_rule_file_fails_open(tmp_path):
    store = RuleStore(tmp_path)
    store.ensure_storage()
    store.rules_path.write_text("not-json", encoding="utf-8")
    service = ToolOptimizerService(store)
    invocation = make_invocation()

    result = await service.optimize(invocation)

    assert result is invocation
    assert result.parameters == {"prompt": "draw a fox", "width": 1024}
