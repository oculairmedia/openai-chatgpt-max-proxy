"""CLI entry point and argument parsing"""

import sys
import argparse
import __main__
from rich.console import Console
import settings
from openai_oauth import TokenManager
from cli.cli_app import OpenAIProxyCLI


console = Console()


def main():
    """Entry point for the CLI"""
    parser = argparse.ArgumentParser(description="OpenAI ChatGPT Max Proxy CLI")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--debug-sse", action="store_true", help="Enable detailed SSE event logging")
    parser.add_argument("--bind", "-b", default=None, help="Override bind address (default: from config)")
    parser.add_argument(
        "--stream-trace",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable raw stream tracing log capture (implies --stream-trace for --debug unless explicitly disabled)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (non-interactive, requires authentication)"
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Don't automatically start server in headless mode"
    )
    parser.add_argument(
        "--reauthenticate",
        action="store_true",
        help="Force re-authentication (clear existing tokens)"
    )

    args = parser.parse_args()

    # Determine stream tracing preference (config default -> CLI overrides)
    stream_trace_setting = settings.STREAM_TRACE_ENABLED
    if args.stream_trace is None:
        if args.debug or args.debug_sse:
            stream_trace_setting = True
    else:
        stream_trace_setting = args.stream_trace

    # Apply overrides to runtime modules
    settings.STREAM_TRACE_ENABLED = stream_trace_setting

    try:
        cli = OpenAIProxyCLI(
            debug=args.debug,
            debug_sse=args.debug_sse,
            bind_address=args.bind,
            stream_trace_enabled=stream_trace_setting
        )

        # Handle reauthentication
        if args.reauthenticate:
            console.print("[yellow]Clearing existing tokens...[/yellow]")
            cli.token_manager.clear_tokens()
            console.print("[green]✓ Tokens cleared. Please authenticate again.[/green]")

        # Run in headless or interactive mode
        if args.headless:
            cli.run_headless_mode(auto_start=not args.no_auto_start)
        else:
            cli.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        console.print("Goodbye!")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {e}")
        if args.debug:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
