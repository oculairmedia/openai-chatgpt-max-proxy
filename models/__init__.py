"""Model registry and specifications package for OpenAI ChatGPT Max Proxy"""

from .specifications import BaseModelSpec, ModelRegistryEntry, BASE_MODELS
from .registry import MODEL_REGISTRY, OPENAI_MODELS_LIST, REASONING_EFFORT_LEVELS
from .resolution import resolve_model_metadata, get_model_entry

__all__ = [
    "BaseModelSpec",
    "ModelRegistryEntry",
    "BASE_MODELS",
    "MODEL_REGISTRY",
    "OPENAI_MODELS_LIST",
    "REASONING_EFFORT_LEVELS",
    "resolve_model_metadata",
    "get_model_entry",
]
