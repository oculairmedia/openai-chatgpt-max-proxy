"""Model name resolution for OpenAI GPT-5 Codex"""

from typing import Tuple, Optional
import logging

from .registry import MODEL_REGISTRY, REASONING_EFFORT_LEVELS

logger = logging.getLogger(__name__)


def resolve_model_metadata(model_name: str) -> Tuple[str, str, str]:
    """
    Resolve model name to Codex API ID and configuration.

    Args:
        model_name: User-provided model name (e.g., "gpt-5-codex", "gpt-5-codex-reasoning-high")
                   Can also be in handle format "provider/model-name" which will be normalized.

    Returns:
        Tuple of (codex_id, reasoning_effort, text_verbosity)

    Examples:
        >>> resolve_model_metadata("gpt-5-codex")
        ("gpt-5-codex", "medium", "medium")

        >>> resolve_model_metadata("gpt-5-codex-reasoning-high")
        ("gpt-5-codex", "high", "medium")

        >>> resolve_model_metadata("gpt-5")
        ("gpt-5", "medium", "low")

        >>> resolve_model_metadata("openai-proxy/gpt-5-codex")
        ("gpt-5-codex", "medium", "medium")
    """
    # Strip provider prefix if present (e.g., "openai-proxy/gpt-5-codex" -> "gpt-5-codex")
    # This handles Letta's handle format: provider/model-name
    if "/" in model_name:
        model_name = model_name.split("/", 1)[-1]
        logger.debug("Extracted model name from handle: %s", model_name)

    # Look up in registry
    entry = MODEL_REGISTRY.get(model_name)

    if entry:
        return (
            entry.codex_id,
            entry.reasoning_effort,
            entry.text_verbosity,
        )

    # Try parsing reasoning suffix (e.g., "gpt-5-codex-reasoning-high")
    if "-reasoning-" in model_name:
        parts = model_name.rsplit("-reasoning-", 1)
        base_model = parts[0]
        reasoning_level = parts[1] if len(parts) > 1 else None

        if reasoning_level in REASONING_EFFORT_LEVELS:
            # Look up base model
            base_entry = MODEL_REGISTRY.get(base_model)
            if base_entry:
                return (
                    base_entry.codex_id,
                    reasoning_level,
                    base_entry.text_verbosity,
                )

        logger.warning(
            "Invalid reasoning level in model name '%s'. Valid levels: %s",
            model_name,
            REASONING_EFFORT_LEVELS,
        )

    # Fallback: Unknown model, use as-is with defaults
    logger.info("Unknown model '%s', using as-is with default config", model_name)
    return (model_name, "medium", "medium")


def get_model_entry(model_name: str) -> Optional[object]:
    """
    Get the full model registry entry.

    Args:
        model_name: Model name to look up

    Returns:
        ModelRegistryEntry if found, None otherwise
    """
    return MODEL_REGISTRY.get(model_name)
