"""
Tests for the event system.
"""

import pytest
from datetime import datetime

from src.events import Event, EventType, EventBus


class TestEventTypes:
    """Tests for Event class."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test_agent",
            data={"task": "test task"}
        )

        assert event.event_type == EventType.AGENT_STARTED
        assert event.agent_id == "test_agent"
        assert event.data["task"] == "test task"
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        event = Event(
            event_type=EventType.FINDING_DISCOVERED,
            agent_id="security_agent",
            data={
                "finding_id": "f1",
                "severity": "critical",
                "title": "SQL Injection"
            }
        )

        d = event.to_dict()

        assert d["event_type"] == "finding_discovered"
        assert d["agent_id"] == "security_agent"
        assert d["data"]["severity"] == "critical"
        assert "timestamp" in d
        assert d["timestamp"].endswith("Z")

    def test_event_from_dict(self):
        """Test event deserialization from dict."""
        data = {
            "event_id": "test-123",
            "event_type": "thinking",
            "agent_id": "coordinator",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {"chunk": "Analyzing code..."}
        }

        event = Event.from_dict(data)

        assert event.event_id == "test-123"
        assert event.event_type == EventType.THINKING
        assert event.agent_id == "coordinator"
        assert event.data["chunk"] == "Analyzing code..."


class TestEventBus:
    """Tests for EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        return EventBus()

    def test_subscribe_and_publish(self, event_bus):
        """Test basic subscribe and publish."""
        received_events = []

        def callback(event):
            received_events.append(event)

        event_bus.subscribe(callback)

        event = Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test",
            data={}
        )

        # Note: This test will need to be updated once EventBus is implemented
        # event_bus.publish_sync(event)
        # assert len(received_events) == 1
        # assert received_events[0].agent_id == "test"

    def test_filtered_subscription(self, event_bus):
        """Test subscribing to specific event types."""
        received_events = []

        def callback(event):
            received_events.append(event)

        # Subscribe only to FINDING_DISCOVERED events
        event_bus.subscribe(callback, EventType.FINDING_DISCOVERED)

        # Publish different event types
        # Note: Update once EventBus is implemented
        # event_bus.publish_sync(Event(EventType.AGENT_STARTED, "a", {}))
        # event_bus.publish_sync(Event(EventType.FINDING_DISCOVERED, "b", {}))
        # event_bus.publish_sync(Event(EventType.THINKING, "c", {}))

        # Should only receive the FINDING_DISCOVERED event
        # assert len(received_events) == 1
        # assert received_events[0].agent_id == "b"

    @pytest.mark.asyncio
    async def test_async_stream_events(self, event_bus):
        """Test async event streaming."""
        # Note: Implement once EventBus is complete
        pass
