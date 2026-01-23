"""
Streaming server for real-time UI updates.

TODO: Implement the streaming server.
"""

from typing import Optional
import asyncio
import json

from ..events import EventBus, Event


class StreamingServer:
    """
    Server that streams events to the UI.

    Supports either:
    - WebSocket connections
    - Server-Sent Events (SSE)

    Choose one approach and implement it.

    TODO: Complete the implementation
    """

    def __init__(self, event_bus: EventBus, host: str = "localhost", port: int = 8080):
        """
        Initialize the streaming server.

        Args:
            event_bus: Event bus to stream events from
            host: Host to bind to
            port: Port to bind to
        """
        self.event_bus = event_bus
        self.host = host
        self.port = port
        self._running = False

    async def start(self) -> None:
        """
        Start the streaming server.

        TODO: Implement server startup
        - Start WebSocket or HTTP server
        - Begin streaming events from event bus
        """
        raise NotImplementedError("Implement streaming server startup")

    async def stop(self) -> None:
        """Stop the streaming server."""
        self._running = False

    async def _handle_websocket(self, websocket, path):
        """
        Handle a WebSocket connection.

        TODO: Implement WebSocket handling
        - Stream events to connected client
        - Handle disconnection gracefully
        """
        raise NotImplementedError("Implement WebSocket handling")

    async def _handle_sse(self, request):
        """
        Handle an SSE connection.

        TODO: Implement SSE handling
        - Return streaming response
        - Format events as SSE
        """
        raise NotImplementedError("Implement SSE handling")


class ConsoleStreamingUI:
    """
    Simple console-based streaming UI for testing.

    This provides a rich terminal interface showing:
    - Agent status
    - Thinking process
    - Tool calls
    - Findings as they're discovered
    """

    def __init__(self, event_bus: EventBus):
        """Initialize the console UI."""
        self.event_bus = event_bus
        self._setup_subscribers()

    def _setup_subscribers(self):
        """Set up event subscriptions."""
        from ..events import EventType

        # Subscribe to all events for display
        self.event_bus.subscribe(self._handle_event, None)

    def _handle_event(self, event: Event) -> None:
        """
        Handle an incoming event.

        TODO: Implement rich console display
        - Use rich library for formatted output
        - Show different event types differently
        - Update status panels
        """
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        # Basic implementation - enhance as needed
        event_type = event.event_type.value
        agent = event.agent_id

        if "thinking" in event_type:
            chunk = event.data.get("chunk", "")
            console.print(f"[dim]{agent}[/dim]: {chunk}", end="")
        elif "finding" in event_type:
            title = event.data.get("title", "Unknown")
            severity = event.data.get("severity", "unknown")
            console.print(Panel(
                f"[bold]{title}[/bold]\nSeverity: {severity}",
                title=f"Finding from {agent}"
            ))
        elif "tool_call" in event_type:
            tool_name = event.data.get("tool_name", "unknown")
            console.print(f"[yellow]{agent}[/yellow] calling tool: {tool_name}")
        elif "started" in event_type:
            task = event.data.get("task", "")
            console.print(f"[green]{agent}[/green] started: {task}")
        elif "completed" in event_type:
            console.print(f"[green]{agent}[/green] completed")
        elif "error" in event_type:
            error = event.data.get("error", "Unknown error")
            console.print(f"[red]{agent} error[/red]: {error}")
