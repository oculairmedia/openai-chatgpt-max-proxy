"""
OAuth token lifecycle management
"""
import json
import os
from pathlib import Path
from typing import Optional

from .token_exchange import TokenResponse, refresh_access_token
from .jwt_utils import extract_chatgpt_account_id


class TokenManager:
    """Manages OAuth token storage and refresh"""

    def __init__(self, token_file: str = ".openai_tokens.json"):
        """
        Initialize token manager.

        Args:
            token_file: Path to token storage file
        """
        self.token_file = Path(token_file)
        self._tokens: Optional[TokenResponse] = None
        self._account_id: Optional[str] = None

    def load_tokens(self) -> bool:
        """
        Load tokens from file.

        Returns:
            True if tokens loaded successfully, False otherwise
        """
        try:
            if not self.token_file.exists():
                print(f"Token file does not exist: {self.token_file}")
                return False

            with open(self.token_file, "r") as f:
                data = json.load(f)

            print(f"Loaded token data from {self.token_file}")
            self._tokens = TokenResponse.from_dict(data)
            print(f"Created TokenResponse from dict")
            self._account_id = extract_chatgpt_account_id(self._tokens.access_token)
            print(f"Extracted account ID: {self._account_id}")

            return True

        except Exception as e:
            print(f"Error loading tokens: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_tokens(self, tokens: TokenResponse) -> bool:
        """
        Save tokens to file.

        Args:
            tokens: Token response to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self._tokens = tokens
            self._account_id = extract_chatgpt_account_id(tokens.access_token)

            # Save to file
            with open(self.token_file, "w") as f:
                json.dump(tokens.to_dict(), f, indent=2)

            # Set restrictive permissions (owner read/write only)
            os.chmod(self.token_file, 0o600)

            return True

        except Exception as e:
            print(f"Error saving tokens: {e}")
            return False

    def get_access_token(self) -> Optional[str]:
        """
        Get current access token.

        Returns:
            Access token if available, None otherwise
        """
        if not self._tokens:
            return None
        return self._tokens.access_token

    def get_account_id(self) -> Optional[str]:
        """
        Get ChatGPT account ID.

        Returns:
            Account ID if available, None otherwise
        """
        return self._account_id

    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated.

        Returns:
            True if tokens are available, False otherwise
        """
        return self._tokens is not None

    def needs_refresh(self) -> bool:
        """
        Check if access token needs refresh.

        Returns:
            True if token is expired or close to expiring, False otherwise
        """
        if not self._tokens:
            return False
        return self._tokens.is_expired()

    async def refresh_if_needed(self) -> bool:
        """
        Refresh access token if needed.

        Returns:
            True if refresh succeeded or not needed, False if refresh failed
        """
        if not self.needs_refresh():
            return True

        if not self._tokens:
            return False

        print("Refreshing access token...")
        new_tokens = await refresh_access_token(self._tokens.refresh_token)

        if not new_tokens:
            print("Failed to refresh access token")
            return False

        self.save_tokens(new_tokens)
        print("Access token refreshed successfully")
        return True

    def clear_tokens(self) -> None:
        """Clear stored tokens and delete token file"""
        self._tokens = None
        self._account_id = None

        if self.token_file.exists():
            self.token_file.unlink()
