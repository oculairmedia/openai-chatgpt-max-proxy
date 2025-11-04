"""
OpenAI OAuth authorization flow with PKCE (from openai/codex CLI)
"""
import base64
import hashlib
import secrets
from typing import Dict, NamedTuple
from urllib.parse import urlencode

from .constants import (
    CLIENT_ID,
    AUTHORIZE_URL,
    REDIRECT_URI,
    SCOPE,
)


class PKCEPair(NamedTuple):
    """PKCE code verifier and challenge pair"""
    verifier: str
    challenge: str


class AuthorizationFlow(NamedTuple):
    """OAuth authorization flow data"""
    pkce: PKCEPair
    state: str
    url: str


def generate_pkce() -> PKCEPair:
    """
    Generate PKCE code verifier and challenge.

    RFC 7636 PKCE standard:
    - Verifier: 43-128 characters, base64url encoded (32 bytes -> 43 chars)
    - Challenge: SHA-256 hash of verifier, base64url encoded

    Returns:
        PKCEPair: Tuple of (verifier, challenge)
    """
    # Generate 32 random bytes -> 43 character base64url verifier
    verifier = secrets.token_urlsafe(32)

    # Create SHA-256 challenge
    challenge_bytes = hashlib.sha256(verifier.encode('utf-8')).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

    return PKCEPair(verifier=verifier, challenge=challenge)


def create_state() -> str:
    """
    Generate random state parameter for CSRF protection.

    Returns:
        str: 32-byte random state string
    """
    return secrets.token_urlsafe(32)


def create_authorization_flow() -> AuthorizationFlow:
    """
    Create OpenAI OAuth authorization flow.

    Generates PKCE pair, state, and authorization URL with all required parameters
    matching the openai/codex CLI behavior.

    Returns:
        AuthorizationFlow: Tuple of (pkce, state, url)
    """
    pkce = generate_pkce()
    state = create_state()

    # Build authorization URL with all parameters
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
        # OpenAI Codex CLI parameters (required for token exchange)
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "codex_cli_rs",
    }

    url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    return AuthorizationFlow(pkce=pkce, state=state, url=url)
