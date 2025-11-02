"""OpenAI GPT-5 Codex model specifications"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass(frozen=True)
class BaseModelSpec:
    """Base specification for GPT-5 Codex models"""
    openai_id: str
    codex_id: str  # Internal Codex API model ID
    created: int
    owned_by: str
    context_length: int
    max_completion_tokens: int
    supports_reasoning: bool = True
    reasoning_effort: str = "medium"  # minimal, low, medium, high
    text_verbosity: str = "medium"  # low, medium


@dataclass(frozen=True)
class ModelRegistryEntry:
    """Registry entry for a specific model variant"""
    openai_id: str
    codex_id: str
    created: int
    owned_by: str
    context_length: int
    max_completion_tokens: int
    reasoning_effort: str = "medium"
    reasoning_summary: str = "auto"  # auto, detailed
    text_verbosity: str = "medium"
    supports_reasoning: bool = True
    include_in_listing: bool = True

    def to_model_listing(self) -> Dict[str, int | str | bool]:
        """Convert to OpenAI model listing format"""
        data: Dict[str, int | str | bool] = {
            "id": self.openai_id,
            "object": "model",
            "type": "model",  # Required by Letta
            "created": self.created,
            "owned_by": self.owned_by,
            "context_length": self.context_length,
            "max_completion_tokens": self.max_completion_tokens,
        }
        if self.supports_reasoning:
            data["reasoning_capable"] = True
            data["reasoning_effort"] = self.reasoning_effort
        return data


# Base GPT-5 Codex models
# Based on opencode-openai-codex-auth reference
BASE_MODELS: List[BaseModelSpec] = [
    BaseModelSpec(
        openai_id="gpt-5-codex",
        codex_id="gpt-5-codex",
        created=1735689600,  # 2025-01-01
        owned_by="openai",
        context_length=128_000,
        max_completion_tokens=32_000,
        supports_reasoning=True,
        reasoning_effort="medium",
        text_verbosity="medium",
    ),
    BaseModelSpec(
        openai_id="gpt-5",
        codex_id="gpt-5",
        created=1735689600,  # 2025-01-01
        owned_by="openai",
        context_length=128_000,
        max_completion_tokens=32_000,
        supports_reasoning=True,
        reasoning_effort="medium",
        text_verbosity="low",  # gpt-5 uses lower verbosity
    ),
    BaseModelSpec(
        openai_id="gpt-5-nano",
        codex_id="gpt-5-nano",
        created=1735689600,  # 2025-01-01
        owned_by="openai",
        context_length=128_000,
        max_completion_tokens=16_000,
        supports_reasoning=True,
        reasoning_effort="minimal",
        text_verbosity="low",
    ),
]
