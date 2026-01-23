"""
Main entry point for the multi-agent code review system.

Usage:
    python -m src.main <path_to_code_file>
    python -m src.main --server  # Start with streaming UI server
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .config import config
from .events import EventBus
from .agents import CoordinatorAgent, SecurityAgent, BugDetectionAgent
from .ui.streaming_server import ConsoleStreamingUI


async def analyze_file(file_path: str, use_streaming_ui: bool = True) -> dict:
    """
    Analyze a code file for security vulnerabilities and bugs.

    Args:
        file_path: Path to the file to analyze
        use_streaming_ui: Whether to show streaming UI

    Returns:
        Analysis results
    """
    # Validate configuration
    config.validate()

    # Read the file
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix not in config.supported_extensions:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    code = path.read_text()

    # Initialize event bus
    event_bus = EventBus()

    # Set up streaming UI if requested
    if use_streaming_ui:
        ui = ConsoleStreamingUI(event_bus)

    # Initialize agents
    coordinator = CoordinatorAgent(event_bus)
    security_agent = SecurityAgent(event_bus)
    bug_agent = BugDetectionAgent(event_bus)

    # Register specialists with coordinator
    coordinator.register_specialist("security", security_agent)
    coordinator.register_specialist("bug", bug_agent)

    # Run analysis
    print(f"\nAnalyzing: {file_path}")
    print("=" * 50)

    results = await coordinator.analyze(code, context={"filename": file_path})

    print("\n" + "=" * 50)
    print("Analysis Complete!")

    return results


async def run_server(host: str = "localhost", port: int = 8080):
    """
    Run the streaming UI server.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    from .ui.streaming_server import StreamingServer

    event_bus = EventBus()
    server = StreamingServer(event_bus, host, port)

    print(f"Starting streaming server on {host}:{port}")
    await server.start()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Code Review System"
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the code file to analyze"
    )

    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the streaming UI server"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for the streaming server"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the streaming server"
    )

    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable streaming UI output"
    )

    args = parser.parse_args()

    if args.server:
        asyncio.run(run_server(args.host, args.port))
    elif args.file:
        results = asyncio.run(analyze_file(args.file, not args.no_ui))

        # Print summary
        print("\n--- Summary ---")
        findings = results.get("findings", [])
        print(f"Total findings: {len(findings)}")

        by_severity = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        for sev, count in sorted(by_severity.items()):
            print(f"  {sev}: {count}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
