"""
Endpoint handlers for the proxy server.
"""
from .health import router as health_router
from .models import router as models_router
from .chat_completions import router as chat_completions_router

__all__ = [
    'health_router',
    'models_router',
    'chat_completions_router',
]

