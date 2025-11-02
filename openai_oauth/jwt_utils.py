"""
JWT token parsing and ChatGPT account ID extraction (from openai/codex CLI)
"""
import base64
import json
from typing import Dict, Optional, Any

from .constants import JWT_CLAIM_PATH, CHATGPT_ACCOUNT_ID_CLAIM


def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token without verification.

    Note: This only decodes the payload, does not verify signature.
    Similar to the openai/codex CLI approach.

    Args:
        token: JWT access token

    Returns:
        Decoded JWT payload as dictionary, or None if invalid
    """
    try:
        # JWT structure: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            print(f"Invalid JWT format: expected 3 parts, got {len(parts)}")
            return None

        # Decode payload (second part)
        payload = parts[1]

        # Add padding if needed (JWT uses base64url without padding)
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += "=" * padding

        # Decode base64
        decoded_bytes = base64.urlsafe_b64decode(payload)
        decoded_str = decoded_bytes.decode("utf-8")

        # Parse JSON
        return json.loads(decoded_str)

    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None


def extract_chatgpt_account_id(access_token: str) -> Optional[str]:
    """
    Extract ChatGPT account ID from JWT access token.

    The account ID is stored in a custom claim path:
    token[JWT_CLAIM_PATH][CHATGPT_ACCOUNT_ID_CLAIM]

    Args:
        access_token: OAuth access token (JWT format)

    Returns:
        ChatGPT account ID if found, None otherwise
    """
    payload = decode_jwt(access_token)
    if not payload:
        return None

    try:
        # Navigate to claim path (e.g., "https://claims.chatgpt.com")
        claims = payload.get(JWT_CLAIM_PATH)
        if not claims:
            print(f"No claims found at path: {JWT_CLAIM_PATH}")
            return None

        # Extract account ID
        account_id = claims.get(CHATGPT_ACCOUNT_ID_CLAIM)
        if not account_id:
            print(f"No account ID found in claim: {CHATGPT_ACCOUNT_ID_CLAIM}")
            return None

        return account_id

    except Exception as e:
        print(f"Error extracting ChatGPT account ID: {e}")
        return None


def get_token_claims(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Get all claims from JWT token for debugging.

    Args:
        access_token: OAuth access token

    Returns:
        Full JWT payload or None if invalid
    """
    return decode_jwt(access_token)
