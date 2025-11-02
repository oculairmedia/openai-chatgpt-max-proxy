"""Main CLI application class for OpenAI ChatGPT Proxy"""

import asyncio
import threading
import webbrowser
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

from openai_oauth import (
    TokenManager,
    create_authorization_flow,
    start_callback_server,
    exchange_code_for_tokens,
    REDIRECT_URI,
)
from proxy import ProxyServer
from cli.debug_setup import setup_debug_console


class OpenAIProxyCLI:
    """Main CLI interface for OpenAI ChatGPT Max Proxy"""

    def __init__(
        self,
        debug: bool = False,
        debug_sse: bool = False,
        bind_address: str = None,
        stream_trace_enabled: bool = False
    ):
        self.token_manager = TokenManager()
        self.proxy_server = ProxyServer(
            debug=debug,
            debug_sse=debug_sse,
            bind_address=bind_address
        )
        self.server_thread: Optional[threading.Thread] = None
        self.server_running = False
        self.debug = debug
        self.debug_sse = debug_sse
        self.bind_address = bind_address or self.proxy_server.bind_address
        self.stream_trace_enabled = stream_trace_enabled

        # Configure debug console
        self.console = setup_debug_console(debug, debug_sse, self.bind_address)

        # Debug mode notifications
        if debug:
            self.console.print("[yellow]Debug mode enabled - verbose logging will be written to proxy_debug.log[/yellow]")
        if debug_sse:
            self.console.print("[yellow]SSE debug mode enabled - detailed streaming events will be logged[/yellow]")
        if stream_trace_enabled:
            self.console.print("[yellow]Stream tracing enabled - raw SSE chunks will be logged to disk[/yellow]")

        # Create event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def clear_screen(self):
        """Clear the terminal screen"""
        self.console.clear()

    def display_header(self):
        """Display application header"""
        self.console.print("\n")
        self.console.print(Panel.fit(
            "[bold cyan]OpenAI ChatGPT Max Proxy[/bold cyan]\n"
            "[dim]Access GPT-5 Codex via ChatGPT Plus/Pro Subscription[/dim]",
            border_style="cyan"
        ))

    def display_status(self):
        """Display authentication and server status"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="cyan", width=20)
        table.add_column()

        # Authentication status
        if self.token_manager.is_authenticated():
            account_id = self.token_manager.get_account_id()
            needs_refresh = self.token_manager.needs_refresh()
            status = "[green]✓ Authenticated[/green]"
            if needs_refresh:
                status += " [yellow](refresh needed)[/yellow]"
            table.add_row("Auth Status:", status)
            if account_id:
                table.add_row("Account ID:", f"[dim]{account_id[:20]}...[/dim]")
        else:
            table.add_row("Auth Status:", "[red]✗ Not authenticated[/red]")

        # Server status
        if self.server_running:
            table.add_row("Server:", f"[green]✓ Running on {self.bind_address}[/green]")
        else:
            table.add_row("Server:", "[dim]Not running[/dim]")

        self.console.print(table)
        self.console.print()

    def display_menu(self):
        """Display main menu options"""
        self.console.print("[bold]Main Menu:[/bold]")
        self.console.print()

        if not self.token_manager.is_authenticated():
            self.console.print("  [cyan]1[/cyan]. Authenticate with ChatGPT")
            self.console.print("  [dim]2. Start Proxy Server (requires authentication)[/dim]")
            self.console.print("  [dim]3. Stop Proxy Server[/dim]")
        else:
            self.console.print("  [cyan]1[/cyan]. Re-authenticate (logout and login)")
            if not self.server_running:
                self.console.print("  [cyan]2[/cyan]. Start Proxy Server")
                self.console.print("  [dim]3. Stop Proxy Server[/dim]")
            else:
                self.console.print("  [dim]2. Start Proxy Server[/dim]")
                self.console.print("  [cyan]3[/cyan]. Stop Proxy Server")

        self.console.print("  [cyan]4[/cyan]. Exit")
        self.console.print()

    async def authenticate(self):
        """Run OpenAI OAuth authentication flow"""
        try:
            self.console.print("\n[bold cyan]OpenAI ChatGPT Authentication[/bold cyan]\n")

            # Create authorization flow
            flow = create_authorization_flow()

            self.console.print("Starting OAuth callback server...")
            callback_server = await start_callback_server(flow.state)

            # Open browser
            self.console.print(f"\n[bold]Opening browser to:[/bold]")
            self.console.print(f"[dim]{flow.url}[/dim]\n")

            try:
                webbrowser.open(flow.url)
                self.console.print("[green]✓ Browser opened[/green]")
            except:
                self.console.print("[yellow]⚠ Could not open browser automatically[/yellow]")
                self.console.print("\nPlease open this URL in your browser:")
                self.console.print(f"[cyan]{flow.url}[/cyan]\n")

            # Wait for callback
            self.console.print("Waiting for authentication...")
            result = await callback_server.wait_for_callback(timeout=300)

            # Stop callback server
            await callback_server.stop()

            if not result:
                self.console.print("[red]✗ Authentication failed or timed out[/red]")
                return False

            # Exchange code for tokens
            self.console.print("Exchanging authorization code for tokens...")
            tokens = await exchange_code_for_tokens(
                result.code,
                flow.pkce.verifier,
                REDIRECT_URI,
            )

            if not tokens:
                self.console.print("[red]✗ Failed to exchange code for tokens[/red]")
                return False

            # Save tokens
            if self.token_manager.save_tokens(tokens):
                account_id = self.token_manager.get_account_id()
                self.console.print("\n[bold green]✓ Authentication successful![/bold green]")
                if account_id:
                    self.console.print(f"[dim]Account ID: {account_id}[/dim]")
                return True
            else:
                self.console.print("[red]✗ Failed to save tokens[/red]")
                return False

        except Exception as e:
            self.console.print(f"[red]✗ Authentication error: {e}[/red]")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False

    def start_server(self):
        """Start the proxy server"""
        if self.server_running:
            self.console.print("[yellow]Server is already running[/yellow]")
            return

        if not self.token_manager.is_authenticated():
            self.console.print("[red]✗ Cannot start server: not authenticated[/red]")
            return

        # Refresh token if needed
        if self.token_manager.needs_refresh():
            self.console.print("[yellow]Refreshing access token...[/yellow]")
            success = self.loop.run_until_complete(self.token_manager.refresh_if_needed())
            if not success:
                self.console.print("[red]✗ Failed to refresh token. Please re-authenticate.[/red]")
                return

        def run_server():
            self.proxy_server.run()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.server_running = True

        self.console.print(f"\n[bold green]✓ Proxy server started on {self.bind_address}[/bold green]\n")

    def stop_server(self):
        """Stop the proxy server"""
        if not self.server_running:
            self.console.print("[yellow]Server is not running[/yellow]")
            return

        self.proxy_server.stop()
        if self.server_thread:
            self.server_thread.join(timeout=5)
        self.server_running = False

        self.console.print("\n[green]✓ Proxy server stopped[/green]\n")

    def run(self):
        """Main CLI loop"""
        # Load existing tokens if available
        self.token_manager.load_tokens()

        while True:
            self.clear_screen()
            self.display_header()
            self.display_status()
            self.display_menu()

            choice = Prompt.ask("Select option", choices=["1", "2", "3", "4"])

            if choice == "1":
                # Authenticate / Re-authenticate
                if self.token_manager.is_authenticated():
                    if Confirm.ask("Logout and re-authenticate?"):
                        self.token_manager.clear_tokens()
                        self.loop.run_until_complete(self.authenticate())
                else:
                    self.loop.run_until_complete(self.authenticate())
                input("\nPress Enter to continue...")

            elif choice == "2":
                # Start server
                self.start_server()
                input("\nPress Enter to continue...")

            elif choice == "3":
                # Stop server
                self.stop_server()
                input("\nPress Enter to continue...")

            elif choice == "4":
                # Exit
                if self.server_running:
                    self.stop_server()
                self.console.print("\n[cyan]Goodbye![/cyan]\n")
                break

    def run_headless_mode(self, auto_start: bool = True):
        """Run in headless mode (non-interactive)"""
        # Load existing tokens
        if not self.token_manager.load_tokens():
            self.console.print("[red]ERROR: No authentication tokens found[/red]")
            self.console.print("Please run authentication first: python cli.py")
            return

        # Refresh if needed
        if self.token_manager.needs_refresh():
            self.console.print("[yellow]Refreshing access token...[/yellow]")
            success = self.loop.run_until_complete(self.token_manager.refresh_if_needed())
            if not success:
                self.console.print("[red]ERROR: Failed to refresh token[/red]")
                return

        # Start server if auto_start is enabled
        if auto_start:
            self.start_server()

            # Keep running
            try:
                while self.server_running:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Shutting down...[/yellow]")
                self.stop_server()
        else:
            self.console.print("[green]Authentication ready. Start server with option 2.[/green]")
