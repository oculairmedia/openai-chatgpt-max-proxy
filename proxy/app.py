"""
FastAPI application initialization and configuration.
"""
import logging
from fastapi import FastAPI

from .middleware import log_requests_middleware
from .endpoints import (
    health_router,
    models_router,
)
from .endpoints.chat_completions import router as chat_completions_router
from .endpoints.responses import router as responses_router

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="OpenAI ChatGPT Max Proxy", version="1.0.0")

# Add middleware
app.middleware("http")(log_requests_middleware)

# Register routers
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_completions_router)
app.include_router(responses_router)

logger.debug("FastAPI application initialized with all routers and middleware")
