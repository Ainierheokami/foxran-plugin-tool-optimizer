from __future__ import annotations

import asyncio
import json
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

    async def fake_apply_rule(invocation, _rule, **_kwargs):
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
async def test_apply_rule_retries_after_model_failure(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    calls = 0

    async def fake_ask_model(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary upstream failure")
        return '{"updates":{"prompt":"draw a cinematic red fox"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(execution={"max_retries": 3})

    result = await service.apply_rule(make_invocation(), rule)

    assert calls == 2
    assert result.parameters["prompt"] == "draw a cinematic red fox"
    assert result.transformations[0]["attempts"] == 2


@pytest.mark.asyncio
async def test_apply_rule_timeout_applies_per_attempt(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    calls = 0

    async def fake_ask_model(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(1)
        return '{"updates":{"prompt":"draw a cinematic red fox"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(execution={"max_retries": 2, "timeout_ms": 500})

    result = await service.apply_rule(make_invocation(), rule)

    assert calls == 2
    assert result.parameters["prompt"] == "draw a cinematic red fox"
    assert result.transformations[0]["attempts"] == 2


@pytest.mark.asyncio
async def test_apply_rule_retries_invalid_json_with_correction(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    captured_messages = []

    async def fake_ask_model(*, messages, **_kwargs):
        captured_messages.append(messages)
        if len(captured_messages) == 1:
            return "not-json"
        return '{"updates":{"prompt":"draw a cinematic red fox"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(execution={"max_retries": 3})

    result = await service.apply_rule(make_invocation(), rule)

    assert len(captured_messages) == 2
    assert "previous optimization attempt failed validation" in captured_messages[1][-1]["content"]
    assert captured_messages[1][-2] == {"role": "assistant", "content": "not-json"}
    assert result.parameters["prompt"] == "draw a cinematic red fox"
    assert result.transformations[0]["attempts"] == 2


@pytest.mark.asyncio
async def test_optimize_fail_open_uses_original_parameters(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    calls = 0

    async def fake_ask_model(**_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    store = RuleStore(tmp_path)
    store.save_rule(make_rule())
    service = ToolOptimizerService(store)

    result = await service.optimize(make_invocation())

    assert result.parameters == {"prompt": "draw a fox", "width": 1024}
    assert result.transformations == []
    assert calls == 3
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

    calls = 0

    async def fake_ask_model(**_kwargs):
        nonlocal calls
        calls += 1
        return '{"updates":{"width":2048}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(targets=[{"path": "width", "mode": "rewrite"}])

    with pytest.raises(ValueError, match="not prompt-like"):
        await service.apply_rule(make_invocation(), rule)

    # The field check cannot change between attempts, so no model call is spent on it.
    assert calls == 0
    assert service.list_recent_runs()[0]["attempts"] == 0


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


def test_extract_urls_stops_at_cjk_text_and_trailing_punctuation():
    from foxran_tool_optimizer_test.backend.service import _extract_urls

    assert _extract_urls("参考 https://a.test/cat.png，画一只猫") == {"https://a.test/cat.png"}
    assert _extract_urls("见https://a.test/x。然后") == {"https://a.test/x"}
    assert _extract_urls("see (https://a.test/x).") == {"https://a.test/x"}
    assert _extract_urls("https://a.test/wiki/Fox_(animal)") == {"https://a.test/wiki/Fox_(animal)"}


@pytest.mark.asyncio
async def test_guardrail_allows_rewriting_cjk_text_next_to_url(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(**_kwargs):
        return '{"updates":{"prompt":"参考 https://a.test/cat.png，画一只毛色蓬松的橘猫"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))

    result = await service.apply_rule(make_invocation("参考 https://a.test/cat.png，画一只猫"), make_rule())

    assert result.parameters["prompt"] == "参考 https://a.test/cat.png，画一只毛色蓬松的橘猫"


@pytest.mark.asyncio
async def test_rule_without_tool_filter_skips_tools_missing_the_field(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(**_kwargs):
        raise AssertionError("no selected field, so no model call")

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    store = RuleStore(tmp_path)
    store.save_rule(
        make_rule(
            match={"tools": [], "sources": []},
            targets=[{"path": "query", "mode": "rewrite"}],
            execution={"failure_policy": "fail_call"},
        )
    )
    service = ToolOptimizerService(store)

    result = await service.optimize(make_invocation())

    assert result.parameters == {"prompt": "draw a fox", "width": 1024}
    assert service.list_recent_runs() == []


@pytest.mark.asyncio
async def test_rule_with_tool_filter_still_requires_rewrite_target(tmp_path):
    service = ToolOptimizerService(RuleStore(tmp_path))
    rule = make_rule(targets=[{"path": "query", "mode": "rewrite"}])

    with pytest.raises(ValueError, match="required target does not exist"):
        await service.apply_rule(make_invocation(), rule)


@pytest.mark.asyncio
async def test_exhausted_budget_stops_retries_and_falls_back(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    calls = 0

    async def fake_ask_model(**_kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(1)
        return '{"updates":{"prompt":"never used"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    monkeypatch.setattr(service_module, "OPTIMIZE_BUDGET_SECONDS", 0.3)
    store = RuleStore(tmp_path)
    store.save_rule(make_rule(execution={"max_retries": 5, "timeout_ms": 10_000}))
    service = ToolOptimizerService(store)

    result = await asyncio.wait_for(service.optimize(make_invocation()), timeout=2)

    assert result.parameters == {"prompt": "draw a fox", "width": 1024}
    assert calls == 1
    run = service.list_recent_runs()[0]
    assert run["success"] is False
    assert run["error"] == "OptimizerBudgetExceeded"


@pytest.mark.asyncio
async def test_unchanged_result_is_recorded_as_run(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    async def fake_ask_model(*, usage, **_kwargs):
        usage["model_name"] = "optimizer-model"
        return '{"updates":{"prompt":"draw a fox"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    invocation = make_invocation()

    result = await service.apply_rule(invocation, make_rule())

    assert result.transformations == []
    run = service.list_recent_runs()[0]
    assert run["success"] is True
    assert run["paths"] == []
    assert run["attempts"] == 1
    assert run["model_name"] == "optimizer-model"


@pytest.mark.asyncio
async def test_array_index_path_and_schema_subset(monkeypatch, tmp_path):
    from foxran_tool_optimizer_test.backend import service as service_module

    captured = {}

    async def fake_ask_model(*, messages, **_kwargs):
        captured["payload"] = json.loads(messages[1]["content"])
        return '{"updates":{"positive_prompts.1":"a misty pine forest"}}'

    monkeypatch.setattr(service_module, "ask_model", fake_ask_model)
    service = ToolOptimizerService(RuleStore(tmp_path))
    invocation = make_invocation()
    invocation.parameters = {"positive_prompts": ["a fox", "forest"], "width": 1024}
    invocation.tool_schema["properties"]["positive_prompts"] = {"type": "array", "items": {"type": "string"}}
    rule = make_rule(targets=[{"path": "positive_prompts.1", "mode": "rewrite"}])

    result = await service.apply_rule(invocation, rule)

    assert result.parameters["positive_prompts"] == ["a fox", "a misty pine forest"]
    assert list(captured["payload"]["tool"]["schema"]["properties"]) == ["positive_prompts"]


def test_active_rules_skip_invalid_entries_and_refresh_after_save(tmp_path):
    store = RuleStore(tmp_path)
    store.ensure_storage()
    valid = make_rule().model_dump(mode="json")
    store.rules_path.write_text(json.dumps([{"id": "broken"}, valid]), encoding="utf-8")

    assert [rule.id for rule in store.load_active_rules()] == ["image-prompt"]

    store.rules_path.write_text(json.dumps([valid]), encoding="utf-8")
    store.save_rule(make_rule(id="second", priority=200))

    assert [rule.id for rule in store.load_active_rules()] == ["image-prompt", "second"]
