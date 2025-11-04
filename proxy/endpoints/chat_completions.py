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

# Load Codex instructions
CODEX_INSTRUCTIONS_FILE = PROJECT_ROOT / "codex_instructions.md"
try:
    with open(CODEX_INSTRUCTIONS_FILE, "r") as f:
        CODEX_INSTRUCTIONS = f.read()
except FileNotFoundError:
    logger.warning(f"Codex instructions file not found at {CODEX_INSTRUCTIONS_FILE}, using default")
    CODEX_INSTRUCTIONS = (
        "You are an expert AI assistant specialized in software development and coding tasks. "
        "Provide clear, accurate, and well-structured code solutions. "
        "Follow best practices and explain your reasoning when appropriate."
    )


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
    # Convert messages to Codex input format
    # Codex API uses "input" array with items of type "message"
    input_items = []
    for msg in request.messages:
        input_item = {
            "type": "message",
            "role": msg.role,
        }

        # Handle content (string or array)
        if isinstance(msg.content, str):
            # Convert string content to input_text format
            input_item["content"] = [{"type": "input_text", "text": msg.content}]
        elif isinstance(msg.content, list):
            # Already in array format - keep as is
            input_item["content"] = msg.content
        else:
            input_item["content"] = []

        # Add tool_calls if present
        if msg.tool_calls:
            input_item["tool_calls"] = [
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
            input_item["tool_call_id"] = msg.tool_call_id

        input_items.append(input_item)

    # Build request body
    body = {
        "model": codex_id,
        "input": input_items,  # Codex uses "input" not "messages"
        "store": False,  # REQUIRED by ChatGPT backend
        "stream": True,  # REQUIRED by ChatGPT backend (always streams, even for non-streaming requests)
    }

    # Add system instructions (required by Codex API)
    # Use provided system message, or official Codex instructions
    if request.system:
        body["instructions"] = request.system
    else:
        # Official Codex instructions from openai/codex repository
        body["instructions"] = CODEX_INSTRUCTIONS

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


async def collect_stream_to_response(
    response: httpx.Response,
    request_id: str,
) -> Dict[str, Any]:
    """
    Collect SSE stream from Codex API and build a complete OpenAI response.

    The Codex API always streams, but clients may request non-streaming.
    This function collects all chunks and assembles them into a complete response.
    """
    collected_content = ""
    collected_tool_calls = []
    finish_reason = None
    usage = None
    model = None

    try:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue

            data = line[6:]  # Remove "data: " prefix

            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)

                # Extract model from first chunk
                if not model and "model" in chunk:
                    model = chunk["model"]

                # Collect deltas
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    choice = chunk["choices"][0]
                    delta = choice.get("delta", {})

                    # Collect content
                    if "content" in delta and delta["content"]:
                        collected_content += delta["content"]

                    # Collect tool calls
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)

                            # Extend list if needed
                            while len(collected_tool_calls) <= idx:
                                collected_tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })

                            tool_call = collected_tool_calls[idx]

                            if "id" in tc_delta:
                                tool_call["id"] = tc_delta["id"]
                            if "type" in tc_delta:
                                tool_call["type"] = tc_delta["type"]
                            if "function" in tc_delta:
                                if "name" in tc_delta["function"]:
                                    tool_call["function"]["name"] = tc_delta["function"]["name"]
                                if "arguments" in tc_delta["function"]:
                                    tool_call["function"]["arguments"] += tc_delta["function"]["arguments"]

                    # Get finish reason
                    if "finish_reason" in choice and choice["finish_reason"]:
                        finish_reason = choice["finish_reason"]

                # Get usage from final chunk
                if "usage" in chunk:
                    usage = chunk["usage"]

            except json.JSONDecodeError:
                logger.warning(f"[{request_id}] Failed to parse SSE chunk: {data[:100]}")
                continue

        # Build complete response
        complete_response = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "gpt-5-codex",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": collected_content or None,
                    },
                    "finish_reason": finish_reason or "stop",
                }
            ],
        }

        # Add tool_calls if any
        if collected_tool_calls:
            complete_response["choices"][0]["message"]["tool_calls"] = collected_tool_calls

        # Add usage if available
        if usage:
            complete_response["usage"] = usage
        else:
            # Estimate usage if not provided
            complete_response["usage"] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        return complete_response

    except Exception as e:
        logger.error(f"[{request_id}] Error collecting stream: {e}")
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
            # Codex API always returns a stream (even when client requested non-streaming)
            logger.info(f"[{request_id}] Making request to Codex API (stream={'yes' if request.stream else 'collect'})...")

            response = await client.post(
                CODEX_API_URL,
                json=codex_request,
                headers=headers,
                timeout=300.0,
            )

            if response.status_code != 200:
                error_text = await response.aread()
                logger.error(f"[{request_id}] Codex API error {response.status_code}: {error_text.decode()}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Codex API error: {error_text.decode()}"
                )

            if request.stream:
                # Client wants streaming - pass through the stream
                return StreamingResponse(
                    stream_codex_response(response, request_id),
                    media_type="text/event-stream",
                )
            else:
                # Client wants non-streaming - collect the stream and return complete response
                logger.debug(f"[{request_id}] Collecting streaming response for non-streaming client")
                complete_response = await collect_stream_to_response(response, request_id)
                elapsed = time.time() - start_time
                logger.info(f"[{request_id}] Request completed in {elapsed:.2f}s")
                return complete_response

    except httpx.TimeoutException:
        logger.error(f"[{request_id}] Request timeout")
        raise HTTPException(status_code=504, detail="Request timeout")

    except Exception as e:
        logger.error(f"[{request_id}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
