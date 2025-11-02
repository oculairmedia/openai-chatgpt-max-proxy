"""Model registry for OpenAI GPT-5 Codex models"""

from typing import Dict, List
import logging

from .specifications import ModelRegistryEntry, BASE_MODELS

logger = logging.getLogger(__name__)

MODEL_REGISTRY: Dict[str, ModelRegistryEntry] = {}
OPENAI_MODELS_LIST: List[Dict[str, int | str | bool]] = []

# Reasoning effort levels for GPT-5 Codex
REASONING_EFFORT_LEVELS = ["minimal", "low", "medium", "high"]


def _register_model(entry: ModelRegistryEntry) -> None:
    """Register a model in the registry"""
    # Avoid accidental overwrites with differing definitions
    existing = MODEL_REGISTRY.get(entry.openai_id)
    if existing and existing != entry:
        logger.debug("Overwriting model registry entry for %s", entry.openai_id)
    MODEL_REGISTRY[entry.openai_id] = entry
    if entry.include_in_listing:
        OPENAI_MODELS_LIST.append(entry.to_model_listing())


def _build_registry() -> None:
    """Build the model registry from base models"""
    for base in BASE_MODELS:
        # Base entry (default reasoning effort)
        base_entry = ModelRegistryEntry(
            openai_id=base.openai_id,
            codex_id=base.codex_id,
            created=base.created,
            owned_by=base.owned_by,
            context_length=base.context_length,
            max_completion_tokens=base.max_completion_tokens,
            reasoning_effort=base.reasoning_effort,
            text_verbosity=base.text_verbosity,
            supports_reasoning=base.supports_reasoning,
        )
        _register_model(base_entry)

        # Reasoning effort variants (e.g., gpt-5-codex-reasoning-low)
        if base.supports_reasoning:
            for effort_level in REASONING_EFFORT_LEVELS:
                reasoning_entry = ModelRegistryEntry(
                    openai_id=f"{base.openai_id}-reasoning-{effort_level}",
                    codex_id=base.codex_id,
                    created=base.created,
                    owned_by=base.owned_by,
                    context_length=base.context_length,
                    max_completion_tokens=base.max_completion_tokens,
                    reasoning_effort=effort_level,
                    text_verbosity=base.text_verbosity,
                    supports_reasoning=True,
                )
                _register_model(reasoning_entry)

        # Alias for Codex API id (no listing)
        if base.openai_id != base.codex_id:
            _register_model(
                ModelRegistryEntry(
                    openai_id=base.codex_id,
                    codex_id=base.codex_id,
                    created=base.created,
                    owned_by=base.owned_by,
                    context_length=base.context_length,
                    max_completion_tokens=base.max_completion_tokens,
                    reasoning_effort=base.reasoning_effort,
                    text_verbosity=base.text_verbosity,
                    supports_reasoning=base.supports_reasoning,
                    include_in_listing=False,
                )
            )


# Build the registry on module import
_build_registry()

# Ensure models list is stable (sorted for deterministic output)
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]
