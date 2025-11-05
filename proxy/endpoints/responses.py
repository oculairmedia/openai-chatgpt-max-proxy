"""
OpenAI Responses API endpoint for GPT-5 Codex API.

This endpoint implements the Responses API (/v1/responses) which is used by
Letta and other clients for GPT-5/reasoning models. It translates Responses API
format (with "input" field) to the same Codex API backend.
"""
import json
import logging
import time
import uuid
import httpx

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional, Union, AsyncIterator
from pydantic import BaseModel

from openai_oauth import TokenManager
from models import resolve_model_metadata
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


# Pydantic models for Responses API
class ResponseInputItem(BaseModel):
    """Input item in Responses API format"""
    type: str = "message"
    role: str
    content: Union[str, List[Dict[str, Any]]]


class ResponseTool(BaseModel):
    """Tool definition in Responses API format"""
    type: str = "function"
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ResponsesAPIRequest(BaseModel):
    """OpenAI Responses API request format"""
    model: str
    input: Optional[Union[str, List[ResponseInputItem]]] = None
    instructions: Optional[str] = None
    tools: Optional[List[ResponseTool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stream: Optional[bool] = None
    store: Optional[bool] = None
    reasoning: Optional[Dict[str, Any]] = None
    text: Optional[Dict[str, Any]] = None


def build_codex_request(
    request: ResponsesAPIRequest,
    codex_id: str,
    reasoning_effort: str,
    text_verbosity: str,
    account_id: str,
) -> Dict[str, Any]:
    """
    Build Codex API request from Responses API format.

    Similar to chat_completions but handles "input" field instead of "messages".
    """
    # Convert input to Codex format
    input_items = []

    if request.input:
        if isinstance(request.input, str):
            # Simple string input - convert to single user message
            input_items.append({
                "type": "message",
                "role": "user",
                "content": request.input,
            })
        elif isinstance(request.input, list):
            # Array of input items
            for item in request.input:
                # Skip tool and system messages (Codex doesn't support them in input)
                if item.role in ["tool", "system"]:
                    continue

                # Handle content (string or array)
                if isinstance(item.content, str):
                    content = item.content
                elif isinstance(item.content, list):
                    # Extract text from content items
                    text_parts = []
                    for content_item in item.content:
                        if isinstance(content_item, dict) and "text" in content_item:
                            text_parts.append(content_item["text"])
                        elif isinstance(content_item, str):
                            text_parts.append(content_item)
                    content = " ".join(text_parts) if text_parts else ""
                else:
                    content = ""

                input_items.append({
                    "type": "message",
                    "role": str(item.role),
                    "content": content,
                })

    # Build request body
    body = {
        "model": codex_id,
        "input": input_items,
        "store": False,  # REQUIRED by ChatGPT backend
        "stream": True,  # REQUIRED by ChatGPT backend
    }

    # Add instructions (REQUIRED by Codex API)
    # Use provided instructions, or official Codex instructions
    if request.instructions:
        body["instructions"] = request.instructions
    else:
        # Official Codex instructions from openai/codex repository
        body["instructions"] = CODEX_INSTRUCTIONS

    # Add tools if provided
    if request.tools:
        body["tools"] = [
            {
                "type": tool.type,
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in request.tools
        ]

    # Add tool_choice if provided
    if request.tool_choice:
        body["tool_choice"] = request.tool_choice

    # Add reasoning configuration (use from request or defaults)
    if request.reasoning:
        body["reasoning"] = request.reasoning
    else:
        body["reasoning"] = {
            "effort": reasoning_effort,
            "summary": "auto",
        }

    # Add text verbosity (use from request or defaults)
    if request.text:
        body["text"] = request.text
    else:
        body["text"] = {
            "verbosity": text_verbosity,
        }

    # Include encrypted reasoning content
    body["include"] = ["reasoning.encrypted_content"]

    return body


async def stream_codex_response(
    response: httpx.Response,
    request_id: str,
) -> AsyncIterator[str]:
    """Stream SSE events from Codex API in Responses API format"""
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
    Collect SSE stream from Codex API and build a complete Responses API response.
    """
    collected_content = ""
    collected_tool_calls = []
    function_calls = {}  # item_id -> {name, arguments}
    finish_reason = None
    usage = None
    model = None
    chunk_count = 0

    try:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue

            data = line[6:]  # Remove "data: " prefix

            if data == "[DONE]":
                logger.debug(f"[{request_id}] Stream done. Collected {chunk_count} chunks")
                break

            try:
                chunk = json.loads(data)
                chunk_count += 1

                # Extract model from response object
                if not model and "response" in chunk and "model" in chunk["response"]:
                    model = chunk["response"]["model"]

                # Handle different event types in Codex streaming format
                event_type = chunk.get("type", "")

                # Collect text deltas
                if event_type == "response.output_text.delta":
                    delta_text = chunk.get("delta", "")
                    if delta_text:
                        collected_content += delta_text

                # Get final text (fallback if deltas missed)
                elif event_type == "response.output_text.done":
                    if "text" in chunk and not collected_content:
                        collected_content = chunk["text"]

                # Handle function call creation
                elif event_type == "response.output_item.added":
                    item = chunk.get("item", {})
                    if item.get("type") == "function_call":
                        item_id = item.get("id")
                        if item_id:
                            function_calls[item_id] = {
                                "name": item.get("name", ""),
                                "arguments": ""
                            }

                # Handle function call arguments delta
                elif event_type == "response.function_call_arguments.delta":
                    item_id = chunk.get("item_id")
                    delta_args = chunk.get("delta", "")
                    if item_id and item_id in function_calls:
                        function_calls[item_id]["arguments"] += delta_args

                # Handle function call completion
                elif event_type == "response.function_call_arguments.done":
                    item_id = chunk.get("item_id")
                    arguments = chunk.get("arguments", "")
                    if item_id and item_id in function_calls:
                        function_calls[item_id]["arguments"] = arguments

                # Handle output item completion
                elif event_type == "response.output_item.done":
                    item = chunk.get("item", {})
                    if item.get("type") == "function_call":
                        item_id = item.get("id")
                        if item_id and item_id in function_calls:
                            if "name" in item:
                                function_calls[item_id]["name"] = item["name"]

                # Handle response completion
                elif event_type == "response.completed":
                    if "response" in chunk:
                        resp = chunk["response"]
                        if "usage" in resp:
                            usage = resp["usage"]
                        finish_reason = "stop"

            except json.JSONDecodeError:
                logger.warning(f"[{request_id}] Failed to parse SSE chunk: {data[:100]}")
                continue

        # Convert Codex function calls to Responses API tool_calls format
        output_items = []

        logger.debug(f"[{request_id}] === COLLECTION COMPLETE ===")
        logger.debug(f"[{request_id}] Collected content length: {len(collected_content)}")
        logger.debug(f"[{request_id}] Function calls collected: {len(function_calls)}")
        logger.debug(f"[{request_id}] Function calls: {json.dumps(function_calls, indent=2)}")

        # Add message item if there's content
        if collected_content:
            output_items.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": collected_content}]
            })
            logger.debug(f"[{request_id}] Added message item with content")

        # Add function call items
        for idx, (item_id, func_call) in enumerate(function_calls.items()):
            if func_call["name"]:
                output_items.append({
                    "id": item_id,
                    "type": "function_call",
                    "name": func_call["name"],
                    "arguments": func_call["arguments"]
                })
                logger.debug(f"[{request_id}] Added function call: {func_call['name']}")

        logger.debug(f"[{request_id}] Total output items: {len(output_items)}")

        # Build complete response in Responses API format
        complete_response = {
            "id": f"resp-{request_id}",
            "object": "response",
            "created_at": int(time.time()),
            "model": model or "gpt-5-codex",
            "output": output_items,
        }

        # Add usage - ensure all fields are integers
        if usage and isinstance(usage, dict):
            complete_response["usage"] = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            }
        else:
            complete_response["usage"] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        return complete_response

    except Exception as e:
        logger.error(f"[{request_id}] Error collecting stream: {e}")
        raise


@router.post("/v1/responses")
async def responses_create(request: ResponsesAPIRequest, raw_request: Request):
    """
    OpenAI-compatible Responses API endpoint for GPT-5 Codex.

    Translates Responses API format (with "input" field) to Codex API.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] ===== NEW RESPONSES API REQUEST =====")
    logger.debug(f"[{request_id}] Model: {request.model}")
    logger.debug(f"[{request_id}] Stream: {request.stream}")
    logger.debug(f"[{request_id}] Has input: {request.input is not None}")
    logger.debug(f"[{request_id}] Tools: {request.tools}")
    logger.debug(f"[{request_id}] Tool choice: {request.tool_choice}")

    # Load and refresh tokens if needed
    if not token_manager.load_tokens():
        logger.error(f"[{request_id}] Failed to load tokens")
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
