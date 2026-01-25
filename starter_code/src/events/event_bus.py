"""
Event bus for publishing and subscribing to events.
Supports both sync and async operations, WebSocket broadcasting.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime

from .event_types import Event, EventType

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    """Represents a subscriber to the event bus."""
    callback: Callable[[Event], Any]
    event_types: Optional[Set[EventType]] = None  # None means all events
    agent_filter: Optional[str] = None  # Filter by specific agent


class EventBus:
    """
    Central event bus for the multi-agent system.
    
    Features:
    - Pub/sub pattern for event distribution
    - Async queue for streaming to UI
    - Support for filtering by event type and agent
    - WebSocket broadcast support
    - Event history for late subscribers
    """
    
    def __init__(self, maxsize: int = 10000, history_size: int = 1000):
        """
        Initialize the event bus.
        
        Args:
            maxsize: Maximum size of the event queue
            history_size: Number of events to keep in history
        """
        self._subscribers: List[Subscriber] = []
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._websockets: Set[Any] = set()
        self._history: List[Event] = []
        self._history_size = history_size
        self._running = True
        self._lock = asyncio.Lock()
        
        # Sync event loop for non-async contexts
        self._sync_loop: Optional[asyncio.AbstractEventLoop] = None
        
    def subscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None,
        agent_filter: Optional[str] = None
    ) -> Subscriber:
        """
        Subscribe to events.
        
        Args:
            callback: Function to call when event is received
            event_types: Optional filter for specific event types
            agent_filter: Optional filter for specific agent
            
        Returns:
            Subscriber object for later unsubscription
        """
        subscriber = Subscriber(
            callback=callback,
            event_types=set(event_types) if event_types else None,
            agent_filter=agent_filter
        )
        self._subscribers.append(subscriber)
        return subscriber
    
    def unsubscribe(self, subscriber: Subscriber) -> None:
        """
        Unsubscribe from events.
        
        Args:
            subscriber: The subscriber to remove
        """
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The event to publish
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]
        
        # Add to queue for streaming
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping oldest event")
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except:
                pass
        
        # Notify subscribers
        for subscriber in self._subscribers:
            if self._should_notify(subscriber, event):
                try:
                    result = subscriber.callback(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
        
        # Broadcast to WebSockets
        await self._broadcast_to_websockets(event)
    
    def publish_sync(self, event: Event) -> None:
        """
        Synchronous version of publish for non-async contexts.
        
        Args:
            event: The event to publish
        """
        # Add to history
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]
        
        # Try to add to queue
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    
        # Notify sync subscribers only
        for subscriber in self._subscribers:
            if self._should_notify(subscriber, event):
                try:
                    result = subscriber.callback(event)
                    # Don't await for sync publish
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
        
        # Schedule WebSocket broadcast
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._broadcast_to_websockets(event))
        except RuntimeError:
            # No running loop, skip WebSocket broadcast
            pass
    
    def _should_notify(self, subscriber: Subscriber, event: Event) -> bool:
        """Check if subscriber should be notified of this event."""
        if subscriber.event_types and event.event_type not in subscriber.event_types:
            return False
        if subscriber.agent_filter and event.agent_id != subscriber.agent_filter:
            return False
        return True
    
    async def get_event(self, timeout: Optional[float] = None) -> Optional[Event]:
        """
        Get the next event from the queue.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            The next event, or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=timeout
                )
            return await self._event_queue.get()
        except asyncio.TimeoutError:
            return None
    
    async def stream_events(self):
        """
        Async generator that yields events as they come in.
        
        Yields:
            Event objects as they are published
        """
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                yield event
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def register_websocket(self, websocket: Any) -> None:
        """Register a WebSocket connection for broadcasts."""
        self._websockets.add(websocket)
    
    def unregister_websocket(self, websocket: Any) -> None:
        """Unregister a WebSocket connection."""
        self._websockets.discard(websocket)
    
    async def _broadcast_to_websockets(self, event: Event) -> None:
        """Broadcast event to all connected WebSockets."""
        if not self._websockets:
            return
            
        message = event.to_json()
        disconnected = set()
        
        for ws in self._websockets:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.debug(f"WebSocket send failed: {e}")
                disconnected.add(ws)
        
        # Remove disconnected sockets
        self._websockets -= disconnected
    
    def get_history(self, 
                    count: Optional[int] = None,
                    event_types: Optional[List[EventType]] = None,
                    agent_filter: Optional[str] = None) -> List[Event]:
        """
        Get events from history.
        
        Args:
            count: Maximum number of events to return
            event_types: Filter by event types
            agent_filter: Filter by agent ID
            
        Returns:
            List of matching events
        """
        events = self._history
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        if agent_filter:
            events = [e for e in events if e.agent_id == agent_filter]
        
        if count:
            events = events[-count:]
        
        return events
    
    def clear(self) -> None:
        """Clear all pending events from the queue."""
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    def clear_history(self) -> None:
        """Clear the event history."""
        self._history = []
    
    def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
    
    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._event_queue.qsize()
    
    @property
    def websocket_count(self) -> int:
        """Get number of connected WebSockets."""
        return len(self._websockets)


# Global event bus instance
event_bus = EventBus()
