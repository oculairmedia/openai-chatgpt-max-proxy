"""
OpenAI chat completions endpoint for GPT-5 Codex API.

This endpoint translates OpenAI-compatible requests to the Codex API format
with store:false (stateless mode) as required by the ChatGPT backend.
"""
import json
import logging
import time
import uuid
import httpx

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncIterator

from openai_oauth import TokenManager
from models import resolve_model_metadata
from ..models import OpenAIChatCompletionRequest
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# Codex API endpoint (ChatGPT backend, not OpenAI Platform API)
CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"

# Global token manager with absolute path
PROJECT_ROOT = Path(__file__).parent.parent.parent
token_manager = TokenManager(str(PROJECT_ROOT / ".openai_tokens.json"))


def build_codex_request(
    request: OpenAIChatCompletionRequest,
    codex_id: str,
    reasoning_effort: str,
    text_verbosity: str,
    account_id: str,
) -> Dict[str, Any]:
    """
    Build Codex API request with store:false.

    Based on opencode-openai-codex-auth reference:
    - store: false (required by ChatGPT backend)
    - No message IDs (stateless mode)
    - reasoning.effort and reasoning.summary
    - text.verbosity
    - include: ["reasoning.encrypted_content"]
    """
    # Convert messages to Codex format
    messages = []
    for msg in request.messages:
        codex_msg = {"role": msg.role}

        # Handle content (string or array)
        if isinstance(msg.content, str):
            codex_msg["content"] = msg.content
        elif isinstance(msg.content, list):
            codex_msg["content"] = msg.content

        # Add tool_calls if present
        if msg.tool_calls:
            codex_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in msg.tool_calls
            ]

        # Add tool_call_id if present (for tool response messages)
        if msg.tool_call_id:
            codex_msg["tool_call_id"] = msg.tool_call_id

        messages.append(codex_msg)

    # Build request body
    body = {
        "model": codex_id,
        "messages": messages,
        "store": False,  # REQUIRED by ChatGPT backend
        "stream": request.stream or False,
    }

    # Add system instructions if provided
    if request.system:
        body["instructions"] = request.system

    # Add tools if provided
    if request.tools:
        body["tools"] = [
            {
                "type": tool.type,
                "function": {
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "parameters": tool.function.parameters,
                }
            }
            for tool in request.tools
        ]

    # Add tool_choice if provided
    if request.tool_choice:
        body["tool_choice"] = request.tool_choice

    # Add reasoning configuration
    body["reasoning"] = {
        "effort": reasoning_effort,
        "summary": "auto",  # auto or detailed
    }

    # Add text verbosity
    body["text"] = {
        "verbosity": text_verbosity,
    }

    # Include encrypted reasoning content for context preservation
    body["include"] = ["reasoning.encrypted_content"]

    # Add optional parameters
    if request.max_tokens:
        body["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.top_p is not None:
        body["top_p"] = request.top_p
    if request.frequency_penalty is not None:
        body["frequency_penalty"] = request.frequency_penalty
    if request.presence_penalty is not None:
        body["presence_penalty"] = request.presence_penalty
    if request.stop:
        body["stop"] = request.stop

    return body


async def stream_codex_response(
    response: httpx.Response,
    request_id: str,
) -> AsyncIterator[str]:
    """Stream SSE events from Codex API"""
    try:
        async for line in response.aiter_lines():
            if not line:
                continue

            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix

                if data == "[DONE]":
                    yield f"data: [DONE]\n\n"
                    break

                try:
                    # Parse and re-emit the chunk
                    chunk = json.loads(data)
                    yield f"data: {json.dumps(chunk)}\n\n"
                except json.JSONDecodeError:
                    logger.warning(f"[{request_id}] Failed to parse SSE data: {data[:100]}")
                    continue

    except Exception as e:
        logger.error(f"[{request_id}] Error streaming response: {e}")
        raise


@router.post("/v1/chat/completions")
async def chat_completions(request: OpenAIChatCompletionRequest, raw_request: Request):
    """
    OpenAI-compatible chat completions endpoint for GPT-5 Codex.

    Translates OpenAI format to Codex API with store:false (stateless mode).
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] ===== NEW CHAT COMPLETION REQUEST =====")
    logger.debug(f"[{request_id}] Model: {request.model}")
    logger.debug(f"[{request_id}] Stream: {request.stream}")
    logger.debug(f"[{request_id}] Messages: {len(request.messages)}")

    # Load and refresh tokens if needed
    logger.debug(f"[{request_id}] Token file path: {token_manager.token_file}")
    logger.debug(f"[{request_id}] Token file exists: {token_manager.token_file.exists()}")

    if not token_manager.load_tokens():
        logger.error(f"[{request_id}] Failed to load tokens from {token_manager.token_file}")
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please authenticate first."
        )

    if token_manager.needs_refresh():
        logger.info(f"[{request_id}] Refreshing access token...")
        success = await token_manager.refresh_if_needed()
        if not success:
            raise HTTPException(
                status_code=401,
                detail="Failed to refresh access token. Please re-authenticate."
            )

    access_token = token_manager.get_access_token()
    account_id = token_manager.get_account_id()

    if not access_token or not account_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Resolve model name to Codex ID and configuration
    codex_id, reasoning_effort, text_verbosity = resolve_model_metadata(request.model)
    logger.debug(f"[{request_id}] Resolved '{request.model}' -> codex_id='{codex_id}', reasoning='{reasoning_effort}', verbosity='{text_verbosity}'")

    # Build Codex API request
    codex_request = build_codex_request(
        request,
        codex_id,
        reasoning_effort,
        text_verbosity,
        account_id,
    )

    logger.debug(f"[{request_id}] Codex request: {json.dumps(codex_request, indent=2)}")

    # Make request to Codex API
    # Headers based on opencode-openai-codex-auth reference
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "chatgpt-account-id": account_id,
        "OpenAI-Beta": "responses=experimental",
        "originator": "codex_cli_rs",
        "session_id": str(uuid.uuid4()),
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            if request.stream:
                # Streaming response
                logger.info(f"[{request_id}] Starting streaming request to Codex API...")

                response = await client.post(
                    CODEX_API_URL,
                    json=codex_request,
                    headers=headers,
                    timeout=300.0,
                )

                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"[{request_id}] Codex API error {response.status_code}: {error_text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Codex API error: {error_text.decode()}"
                    )

                return StreamingResponse(
                    stream_codex_response(response, request_id),
                    media_type="text/event-stream",
                )

            else:
                # Non-streaming response
                logger.info(f"[{request_id}] Making non-streaming request to Codex API...")

                response = await client.post(
                    CODEX_API_URL,
                    json=codex_request,
                    headers=headers,
                    timeout=300.0,
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"[{request_id}] Codex API error {response.status_code}: {error_text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Codex API error: {error_text}"
                    )

                result = response.json()
                elapsed = time.time() - start_time
                logger.info(f"[{request_id}] Request completed in {elapsed:.2f}s")

                return result

    except httpx.TimeoutException:
        logger.error(f"[{request_id}] Request timeout")
        raise HTTPException(status_code=504, detail="Request timeout")

    except Exception as e:
        logger.error(f"[{request_id}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
