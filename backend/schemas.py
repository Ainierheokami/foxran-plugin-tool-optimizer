from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class RuleMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)


class RuleTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    mode: Literal["rewrite", "rewrite_if_present"] = "rewrite"


class ModelSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[str] = Field(default_factory=list)
    fallback_tags: list[str] = Field(default_factory=list)


class OptimizerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_selector: ModelSelector = Field(default_factory=ModelSelector)
    system_prompt: str = ""
    instruction_template: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=64, le=32768)


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: int = Field(default=15_000, ge=500, le=120_000)
    max_retries: int = Field(default=3, ge=1, le=5)
    failure_policy: Literal["use_original", "fail_call"] = "use_original"
    max_input_chars: int = Field(default=12_000, ge=100, le=200_000)


class GuardrailSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preserve_urls: bool = True
    preserve_references: bool = True
    deny_sensitive_fields: bool = True
    allow_unsafe_fields: bool = False


class OptimizationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = Field(min_length=1)
    enabled: bool = True
    priority: int = Field(default=100, ge=-10_000, le=10_000)
    match: RuleMatch = Field(default_factory=RuleMatch)
    targets: list[RuleTarget] = Field(default_factory=list, min_length=1)
    optimizer: OptimizerSettings = Field(default_factory=OptimizerSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean or not SAFE_ID_RE.fullmatch(clean):
            raise ValueError("rule id only supports letters, numbers, dots, dashes, and underscores")
        return clean


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: OptimizationRule
    tool_name: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
