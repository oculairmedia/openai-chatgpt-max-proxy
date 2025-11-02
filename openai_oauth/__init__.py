"""
OpenAI OAuth authentication module
"""
from .constants import (
    CLIENT_ID,
    AUTHORIZE_URL,
    TOKEN_URL,
    REDIRECT_URI,
    SCOPE,
    JWT_CLAIM_PATH,
    CHATGPT_ACCOUNT_ID_CLAIM,
    OAUTH_CALLBACK_PORT,
    OAUTH_CALLBACK_PATH,
)
from .authorization import (
    PKCEPair,
    AuthorizationFlow,
    generate_pkce,
    create_state,
    create_authorization_flow,
)
from .token_exchange import (
    TokenResponse,
    exchange_code_for_tokens,
    refresh_access_token,
)
from .jwt_utils import (
    decode_jwt,
    extract_chatgpt_account_id,
    get_token_claims,
)
from .callback_server import (
    CallbackResult,
    OAuthCallbackServer,
    start_callback_server,
)
from .token_manager import TokenManager

__all__ = [
    # Constants
    "CLIENT_ID",
    "AUTHORIZE_URL",
    "TOKEN_URL",
    "REDIRECT_URI",
    "SCOPE",
    "JWT_CLAIM_PATH",
    "CHATGPT_ACCOUNT_ID_CLAIM",
    "OAUTH_CALLBACK_PORT",
    "OAUTH_CALLBACK_PATH",
    # Authorization
    "PKCEPair",
    "AuthorizationFlow",
    "generate_pkce",
    "create_state",
    "create_authorization_flow",
    # Token Exchange
    "TokenResponse",
    "exchange_code_for_tokens",
    "refresh_access_token",
    # JWT Utilities
    "decode_jwt",
    "extract_chatgpt_account_id",
    "get_token_claims",
    # Callback Server
    "CallbackResult",
    "OAuthCallbackServer",
    "start_callback_server",
    # Token Manager
    "TokenManager",
]
