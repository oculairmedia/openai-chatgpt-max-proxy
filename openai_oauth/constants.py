"""
OpenAI OAuth constants (from openai/codex CLI)
"""

# OAuth Configuration
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"

# JWT claim path for ChatGPT account ID
JWT_CLAIM_PATH = "https://claims.chatgpt.com"
CHATGPT_ACCOUNT_ID_CLAIM = "chatgpt_account_id"

# OAuth callback server
OAUTH_CALLBACK_PORT = 1455
OAUTH_CALLBACK_PATH = "/auth/callback"
