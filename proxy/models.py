"""
Pydantic models for OpenAI API compatibility.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel


class OpenAIFunctionCall(BaseModel):
    """Function call in a tool call"""
    name: str
    arguments: str  # JSON string


class OpenAIToolCall(BaseModel):
    """Tool call from assistant"""
    id: str
    type: str = "function"
    function: OpenAIFunctionCall


class OpenAIMessage(BaseModel):
    """Chat message"""
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    tool_calls: Optional[List[OpenAIToolCall]] = None
    tool_call_id: Optional[str] = None  # For tool response messages


class OpenAIFunction(BaseModel):
    """Function definition"""
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class OpenAITool(BaseModel):
    """Tool definition"""
    type: str = "function"
    function: OpenAIFunction


class OpenAIChatCompletionRequest(BaseModel):
    """OpenAI chat completion request"""
    model: str
    messages: List[OpenAIMessage]
    max_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None  # Accept but ignore (not supported by Codex API)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    stream: Optional[bool] = False
    tools: Optional[List[OpenAITool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    system: Optional[str] = None  # System message
