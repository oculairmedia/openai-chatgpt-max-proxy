# Development Roadmap - OpenAI ChatGPT Max Proxy

## Project Overview
Sister project to [anthropic-claude-max-proxy](https://github.com/oculairmedia/anthropic-claude-max-proxy), providing OAuth access to ChatGPT Plus/Pro subscription via API.

**Repository**: https://github.com/oculairmedia/openai-chatgpt-max-proxy  
**Reference Implementation**: https://github.com/numman-ali/opencode-openai-codex-auth

## Phase 1: OAuth Infrastructure ✅ NEXT

### 1.1 OpenAI OAuth Module
**Files to create/modify:**
- `/oauth/openai_authorization.py` - OAuth flow for OpenAI
- `/oauth/openai_token_exchange.py` - Code → token exchange
- `/oauth/openai_token_manager.py` - Token lifecycle with account ID
- `/settings.py` - Add OpenAI OAuth configuration

**Key differences from Anthropic:**
```python
# OpenAI OAuth endpoints
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"  # Different port!

# NEW: Extract ChatGPT account ID from JWT
def extract_account_id(access_token: str) -> str:
    payload = jwt.decode(access_token, options={"verify_signature": False})
    return payload["https://claims.chatgpt.com"]["chatgpt_account_id"]
```

### 1.2 CLI Authentication
**Files to modify:**
- `/cli.py` - Add OpenAI auth option
- `/cli/auth_handlers.py` - OpenAI auth flow

**Flow:**
1. Generate PKCE challenge
2. Start local server on port 1455 (not 8080!)
3. Open browser to OpenAI auth
4. Exchange code for tokens
5. Extract account ID from JWT
6. Save tokens + account ID

## Phase 2: Model Registry

### 2.1 OpenAI Model Definitions
**Files to create:**
- `/models/openai_specifications.py` - GPT-5 Codex model specs
- `/models/openai_registry.py` - Model lookup and resolution

**Model List:**
```python
GPT5_CODEX_MODELS = [
    {
        "id": "gpt-5-codex-low",
        "name": "GPT-5 Codex Low",
        "openai_id": "gpt-5-codex",
        "reasoning_effort": "low",
        "context_window": 128000,
    },
    {
        "id": "gpt-5-codex-medium",
        "name": "GPT-5 Codex Medium",
        "openai_id": "gpt-5-codex",
        "reasoning_effort": "medium",
        "context_window": 128000,
    },
    {
        "id": "gpt-5-codex-high",
        "name": "GPT-5 Codex High",
        "openai_id": "gpt-5-codex",
        "reasoning_effort": "high",
        "context_window": 128000,
    },
    # ... gpt-5 variants
]
```

## Phase 3: API Endpoints

### 3.1 Chat Completions Endpoint
**Files to create:**
- `/proxy/endpoints/openai_native_chat.py` - `/v1/chat/completions`

**Critical requirements:**
```python
@router.post("/v1/chat/completions")
async def openai_chat_completions(request: ChatCompletionRequest):
    # 1. ENFORCE store:false (REQUIRED by ChatGPT backend)
    request_body["store"] = False

    # 2. Add ChatGPT account ID header
    headers = {
        "Authorization": f"Bearer {access_token}",
        "openai-conversation-id": account_id,  # CRITICAL!
    }

    # 3. Map reasoning_effort from model variant
    if model_config.reasoning_capable:
        request_body["reasoning_effort"] = model_config.reasoning_effort

    # 4. Proxy to api.openai.com
    response = await client.post(
        "https://api.openai.com/v1/chat/completions",
        json=request_body,
        headers=headers
    )
```

### 3.2 Models Endpoint Update
**Files to modify:**
- `/proxy/endpoints/models.py`

Add OpenAI models to list:
```python
{
    "id": "gpt-5-codex-medium",
    "object": "model",
    "type": "model",  # For Letta compatibility
    "created": 1234567890,
    "owned_by": "openai",
    "provider": "openai",
}
```

## Phase 4: System Instructions

### 4.1 Codex Instructions Fetcher
**Files to create:**
- `/prompts/fetch_codex_instructions.py`

Fetch from OpenAI's official Codex repo:
```python
CODEX_INSTRUCTIONS_URL = "https://raw.githubusercontent.com/openai/codex/refs/heads/main/.codex/instructions.md"

async def fetch_codex_instructions():
    # Use ETag caching
    # Save to prompts/codex_instructions.md
    # Inject as "developer" role messages
```

## Phase 5: Request Transformation

### 5.1 Message Injection
**Files to create:**
- `/openai_compat/message_transformer.py`

```python
def inject_codex_instructions(messages: list) -> list:
    instructions = load_cached_instructions()
    return [
        {"role": "developer", "content": instructions},
        *messages
    ]
```

## Phase 6: Configuration & Settings

### 6.1 Port Configuration
**Update settings.py:**
```python
# Use port 8083 (Claude uses 8082)
OPENAI_PROXY_PORT = 8083
OAUTH_CALLBACK_PORT = 1455  # OpenAI standard
```

### 6.2 Environment Variables
```bash
# .env additions
OPENAI_OAUTH_ACCESS_TOKEN=eyJ...
OPENAI_OAUTH_REFRESH_TOKEN=ey-...
OPENAI_CHATGPT_ACCOUNT_ID=user-abc123...
```

## Phase 7: Testing & Integration

### 7.1 OAuth Testing
- Test authentication flow
- Test token refresh
- Test account ID extraction

### 7.2 API Testing
- Test chat completions endpoint
- Test store:false enforcement
- Test reasoning variants
- Test streaming

### 7.3 Letta Integration
- Test model discovery
- Test chat functionality
- Test conversation continuity

## Technical Differences from Claude Proxy

| Feature | Claude Proxy | ChatGPT Proxy |
|---------|--------------|---------------|
| OAuth Endpoint | auth.anthropic.com | auth.openai.com |
| Callback Port | 8080 | 1455 |
| API Endpoint | /v1/messages | /v1/chat/completions |
| Stateless Mode | Optional | **Required** (store:false) |
| Account Header | anthropic-client-sha | openai-conversation-id |
| Account ID Source | Config | **JWT token claim** |
| System Role | "system" | "developer" |
| Reasoning Param | thinking.budget_tokens | reasoning_effort |
| Proxy Port | 8082 | 8083 |

## Next Steps

1. ✅ Create repository
2. ✅ Initial README
3. ⬜ Implement OpenAI OAuth module
4. ⬜ Update CLI for OpenAI auth
5. ⬜ Create model registry
6. ⬜ Implement chat completions endpoint
7. ⬜ Fetch Codex instructions
8. ⬜ Test with Letta
9. ⬜ Documentation
10. ⬜ Release v1.0

## References

- [opencode-openai-codex-auth](https://github.com/numman-ali/opencode-openai-codex-auth) - Reference implementation
- [OpenAI Codex CLI](https://github.com/openai/codex) - Official Codex CLI source
- [anthropic-claude-max-proxy](https://github.com/oculairmedia/anthropic-claude-max-proxy) - Sister project
