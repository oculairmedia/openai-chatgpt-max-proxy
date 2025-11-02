"""
Local OAuth callback server (from openai/codex CLI)
"""
import asyncio
from typing import Optional, Dict
from urllib.parse import parse_qs, urlparse
from aiohttp import web

from .constants import OAUTH_CALLBACK_PORT, OAUTH_CALLBACK_PATH


class CallbackResult:
    """OAuth callback result"""

    def __init__(self, code: str, state: str):
        self.code = code
        self.state = state


class OAuthCallbackServer:
    """Local HTTP server for OAuth callback"""

    def __init__(self, expected_state: str):
        self.expected_state = expected_state
        self.result: Optional[CallbackResult] = None
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self._event = asyncio.Event()

        # Register callback route
        self.app.router.add_get(OAUTH_CALLBACK_PATH, self._handle_callback)

    async def _handle_callback(self, request: web.Request) -> web.Response:
        """Handle OAuth callback request"""
        try:
            # Parse query parameters
            code = request.query.get("code")
            state = request.query.get("state")
            error = request.query.get("error")
            error_description = request.query.get("error_description")

            # Check for errors
            if error:
                print(f"OAuth error: {error}")
                if error_description:
                    print(f"Description: {error_description}")

                return web.Response(
                    text=f"""
                    <html>
                        <body>
                            <h1>Authentication Failed</h1>
                            <p>Error: {error}</p>
                            <p>{error_description or ''}</p>
                            <p>You can close this window.</p>
                        </body>
                    </html>
                    """,
                    content_type="text/html",
                    status=400,
                )

            # Validate required parameters
            if not code or not state:
                return web.Response(
                    text="Missing code or state parameter",
                    status=400,
                )

            # Validate state (CSRF protection)
            if state != self.expected_state:
                print(f"State mismatch: expected {self.expected_state}, got {state}")
                return web.Response(
                    text="Invalid state parameter",
                    status=400,
                )

            # Store result
            self.result = CallbackResult(code=code, state=state)
            self._event.set()

            # Return success page
            return web.Response(
                text="""
                <html>
                    <body>
                        <h1>Authentication Successful!</h1>
                        <p>You can now close this window and return to the terminal.</p>
                        <script>
                            setTimeout(function() {
                                window.close();
                            }, 2000);
                        </script>
                    </body>
                </html>
                """,
                content_type="text/html",
            )

        except Exception as e:
            print(f"Error in callback handler: {e}")
            return web.Response(
                text=f"Internal error: {e}",
                status=500,
            )

    async def start(self) -> None:
        """Start the callback server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(
            self.runner,
            host="localhost",
            port=OAUTH_CALLBACK_PORT,
        )

        await site.start()
        print(f"OAuth callback server listening on port {OAUTH_CALLBACK_PORT}")

    async def wait_for_callback(self, timeout: int = 300) -> Optional[CallbackResult]:
        """
        Wait for OAuth callback.

        Args:
            timeout: Maximum time to wait in seconds (default 5 minutes)

        Returns:
            CallbackResult if successful, None if timeout or error
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return self.result
        except asyncio.TimeoutError:
            print(f"OAuth callback timeout after {timeout} seconds")
            return None

    async def stop(self) -> None:
        """Stop the callback server"""
        if self.runner:
            await self.runner.cleanup()


async def start_callback_server(expected_state: str) -> OAuthCallbackServer:
    """
    Start OAuth callback server.

    Args:
        expected_state: Expected state parameter for CSRF protection

    Returns:
        OAuthCallbackServer instance
    """
    server = OAuthCallbackServer(expected_state)
    await server.start()
    return server
