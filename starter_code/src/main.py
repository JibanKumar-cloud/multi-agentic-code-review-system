"""
Main entry point for the multi-agent code review system.

Usage:
    python -m src.main <path_to_code_file>       # Analyze a file
    python -m src.main --server                   # Start web server
    python -m src.main --server --port 8080       # Start on specific port
"""

import argparse
import asyncio
import sys
import json
from pathlib import Path

import uvicorn
from .ui import app

from .config import config
from .events import EventBus
from .agents.code_review_workflow import CodeReviewWorkflow


async def analyze_file(file_path: str, output_json: bool = False) -> dict:
    """
    Analyze a code file for security vulnerabilities and bugs.
    
    Args:
        file_path: Path to the file to analyze
        output_json: Whether to output JSON format
        
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
    
    # Set up console output if not JSON mode
    if not output_json:
        def print_event(event):
            if event.event_type.value == "thinking":
                print(event.data.get("chunk", ""), end="", flush=True)
            elif event.event_type.value == "agent_started":
                print(f"\n🚀 {event.agent_id}: {event.data.get('task', '')}")
            elif event.event_type.value == "agent_completed":
                print(f"\n✅ {event.agent_id}: {event.data.get('summary', '')}")
            elif event.event_type.value == "finding_discovered":
                sev = event.data.get('severity', 'medium')
                print(f"\n⚠️  [{sev.upper()}] {event.data.get('title', 'Finding')}")
                print(f"   Line {event.data.get('location', {}).get('line_start', '?')}: {event.data.get('description', '')}")
        
        event_bus.subscribe(print_event)
    

    code_review_wf = CodeReviewWorkflow(event_bus)
    
    # Run analysis
    if not output_json:
        print(f"\n{'='*60}")
        print(f"Analyzing: {file_path}")
        print(f"{'='*60}")
    
    results = await code_review_wf.review_code(code, filename={"filename": str(path)})
    
    if not output_json:
        print(f"\n{'='*60}")
        print("Analysis Complete!")
        print(f"{'='*60}")
        
        # Print summary
        print(f"\n📊 Summary:")
        print(f"   Total findings: {len(results.get('findings', []))}")
        
        by_severity = results.get('metrics', {}).get('by_severity', {})
        for sev in ['critical', 'high', 'medium', 'low']:
            count = by_severity.get(sev, 0)
            if count > 0:
                print(f"   {sev.capitalize()}: {count}")
    
    return results


async def run_server(host: str = "0.0.0.0", port: int = 8080):
    """
    Run the streaming UI server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
    """
    
    print(f"\n🚀 Starting Multi-Agent Code Review Server")
    print(f"   URL: http://{host}:{port}")
    print(f"   Press Ctrl+C to stop\n")
    
    uvicorn_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Code Review System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main code.py           # Analyze a file
  python -m src.main --server          # Start web server
  python -m src.main code.py --json    # Output JSON results
        """
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
        default="0.0.0.0",
        help="Host for the streaming server (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the streaming server (default: 8080)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    try:
        if args.server:
            asyncio.run(run_server(args.host, args.port))
        elif args.file:
            results = asyncio.run(analyze_file(args.file, args.json))
            
            if args.json:
                print(json.dumps(results, indent=2, default=str))
            else:
                # Print final finding details
                findings = results.get('findings', [])
                if findings:
                    print(f"\n📋 Detailed Findings:\n")
                    for i, f in enumerate(findings, 1):
                        print(f"{i}. [{f.get('severity', 'medium').upper()}] {f.get('title', 'Finding')}")
                        print(f"   Category: {f.get('category', 'unknown')}")
                        print(f"   Type: {f.get('type', 'unknown')}")
                        loc = f.get('location', {})
                        print(f"   Location: {loc.get('file', '?')}:{loc.get('line_start', '?')}")
                        print(f"   {f.get('description', '')}")
                        print()
        else:
            parser.print_help()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
