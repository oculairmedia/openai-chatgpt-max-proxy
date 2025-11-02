"""
OpenAI OAuth token exchange (from openai/codex CLI)
"""
import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta

from .constants import TOKEN_URL, CLIENT_ID


class TokenResponse:
    """OAuth token response"""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        token_type: str = "Bearer",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.expires_in = expires_in
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)

    def is_expired(self) -> bool:
        """Check if access token is expired (with 5 minute buffer)"""
        buffer = timedelta(minutes=5)
        return datetime.now() >= (self.expires_at - buffer)

    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for storage"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> "TokenResponse":
        """Load from dictionary"""
        token = cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            token_type=data.get("token_type", "Bearer"),
        )
        if "expires_at" in data:
            token.expires_at = datetime.fromisoformat(data["expires_at"])
        return token


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> Optional[TokenResponse]:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from callback
        code_verifier: PKCE code verifier
        redirect_uri: OAuth redirect URI

    Returns:
        TokenResponse if successful, None otherwise
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code != 200:
                print(f"Token exchange failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None

            data = response.json()

            return TokenResponse(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
                token_type=data.get("token_type", "Bearer"),
            )

        except Exception as e:
            print(f"Error during token exchange: {e}")
            return None


async def refresh_access_token(refresh_token: str) -> Optional[TokenResponse]:
    """
    Refresh access token using refresh token.

    Args:
        refresh_token: OAuth refresh token

    Returns:
        TokenResponse if successful, None otherwise
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                    "refresh_token": refresh_token,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

            if response.status_code != 200:
                print(f"Token refresh failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None

            data = response.json()

            return TokenResponse(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),  # May not return new refresh token
                expires_in=data["expires_in"],
                token_type=data.get("token_type", "Bearer"),
            )

        except Exception as e:
            print(f"Error during token refresh: {e}")
            return None
