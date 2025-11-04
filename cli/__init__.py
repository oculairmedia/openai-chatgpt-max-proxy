"""CLI package for OpenAI ChatGPT Max Proxy

This package provides a modular command-line interface for managing
the OpenAI ChatGPT Max Proxy server.
"""

from cli.cli_app import OpenAIProxyCLI
from cli.main import main

__all__ = [
    "OpenAIProxyCLI",
    "main",
]
