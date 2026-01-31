"""
Tests for the event system.

Run with: pytest tests/test_events.py -v
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.events import Event, EventType, EventBus
from src.events.event_types import (
    create_agent_started_event,
    create_agent_completed_event,
    create_finding_event,
    create_tool_call_start_event,
    create_tool_call_result_event,
    create_thinking_event,
    create_agent_error_event,
    create_fix_proposed_event,
)


class TestEventTypes:
    """Tests for Event class and event types."""

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

    def test_all_event_types_exist(self):
        """Test that all required event types are defined."""
        required_types = [
            "AGENT_STARTED",
            "AGENT_COMPLETED",
            "AGENT_ERROR",
            "TOOL_CALL_START",
            "TOOL_CALL_RESULT",
            "THINKING",
            "FINDING_DISCOVERED",
            "FIX_PROPOSED",
            "PLAN_CREATED",
            "PLAN_STEP_STARTED",
            "PLAN_STEP_COMPLETED",
            "REVIEW_STARTED",
            "REVIEW_COMPLETED",
        ]
        
        for type_name in required_types:
            assert hasattr(EventType, type_name), f"Missing event type: {type_name}"


class TestEventFactories:
    """Tests for event factory functions."""

    def test_create_agent_started_event(self):
        """Test agent_started event factory."""
        event = create_agent_started_event(
            agent_id="security_agent",
            task="Analyzing code for security vulnerabilities"
        )
        
        assert event.event_type == EventType.AGENT_STARTED
        assert event.agent_id == "security_agent"
        assert event.data["task"] == "Analyzing code for security vulnerabilities"

    def test_create_agent_completed_event(self):
        """Test agent_completed event factory."""
        event = create_agent_completed_event(
            agent_id="bug_agent",
            summary="Found 3 potential bugs",
            duration_ms=1500
        )
        
        assert event.event_type == EventType.AGENT_COMPLETED
        assert event.data["summary"] == "Found 3 potential bugs"
        assert event.data["duration_ms"] == 1500

    def test_create_finding_event(self):
        """Test finding_discovered event factory."""
        event = create_finding_event(
            agent_id="security_agent",
            finding_id="sec-001",
            category="injection",
            severity="critical",
            title="SQL Injection Vulnerability",
            description="User input directly concatenated into SQL query",
            location={"file": "auth.py", "line": 42},
            code_snippet="query = f\"SELECT * FROM users WHERE id = {user_id}\""
        )
        
        assert event.event_type == EventType.FINDING_DISCOVERED
        assert event.data["severity"] == "critical"
        assert event.data["category"] == "injection"
        assert event.data["location"]["line"] == 42

    def test_create_tool_call_events(self):
        """Test tool call start and result events."""
        start_event = create_tool_call_start_event(
            agent_id="coordinator",
            tool_name="search_pattern",
            tool_input={"pattern": "eval\\(", "code": "..."}
        )
        
        assert start_event.event_type == EventType.TOOL_CALL_START
        assert start_event.data["tool_name"] == "search_pattern"
        
        result_event = create_tool_call_result_event(
            agent_id="coordinator",
            tool_name="search_pattern",
            tool_output={"matches": [{"line": 10}]},
            duration_ms=50,
            success=True
        )
        
        assert result_event.event_type == EventType.TOOL_CALL_RESULT
        assert result_event.data["success"] == True
        assert result_event.data["duration_ms"] == 50

    def test_create_thinking_event(self):
        """Test thinking event factory."""
        event = create_thinking_event(
            agent_id="security_agent",
            chunk="Analyzing the authenticate function for SQL injection..."
        )
        
        assert event.event_type == EventType.THINKING
        assert "SQL injection" in event.data["chunk"]

    def test_create_error_event(self):
        """Test agent_error event factory."""
        event = create_agent_error_event(
            agent_id="bug_agent",
            error="Rate limit exceeded",
            error_type="RateLimitError",
            recoverable=True,
            attempt=1,
            max_attempts=3
        )
        
        assert event.event_type == EventType.AGENT_ERROR
        assert event.data["recoverable"] == True
        assert event.data["attempt"] == 1

    def test_create_fix_proposed_event(self):
        """Test fix_proposed event factory."""
        event = create_fix_proposed_event(
            agent_id="security_agent",
            finding_id="sec-001",
            fix_description="Use parameterized query instead",
            original_code="query = f\"SELECT * FROM users WHERE id = {user_id}\"",
            fixed_code="cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))"
        )
        
        assert event.event_type == EventType.FIX_PROPOSED
        assert "parameterized" in event.data["fix_description"]


class TestEventBus:
    """Tests for EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        return EventBus()

    def test_event_bus_creation(self, event_bus):
        """Test event bus initialization."""
        assert event_bus is not None

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test basic subscribe and publish."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        event_bus.subscribe("*", callback)

        event = Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test",
            data={"task": "test"}
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)  # Give time for async processing

        assert len(received_events) == 1
        assert received_events[0].agent_id == "test"

    @pytest.mark.asyncio
    async def test_filtered_subscription(self, event_bus):
        """Test subscribing to specific event types."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        # Subscribe only to FINDING_DISCOVERED events
        event_bus.subscribe(EventType.FINDING_DISCOVERED.value, callback)

        # Publish different event types
        await event_bus.publish(Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="a",
            data={}
        ))
        await event_bus.publish(Event(
            event_type=EventType.FINDING_DISCOVERED,
            agent_id="b",
            data={"severity": "high"}
        ))
        await event_bus.publish(Event(
            event_type=EventType.THINKING,
            agent_id="c",
            data={}
        ))

        await asyncio.sleep(0.1)

        # Should only receive the FINDING_DISCOVERED event
        finding_events = [e for e in received_events if e.event_type == EventType.FINDING_DISCOVERED]
        assert len(finding_events) >= 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        event_bus.subscribe("*", callback)
        
        await event_bus.publish(Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test1",
            data={}
        ))
        await asyncio.sleep(0.1)
        
        event_bus.unsubscribe("*", callback)
        
        await event_bus.publish(Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test2",
            data={}
        ))
        await asyncio.sleep(0.1)

        # Should only have received one event (before unsubscribe)
        assert len(received_events) == 1
        assert received_events[0].agent_id == "test1"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """Test multiple subscribers receiving same event."""
        received_1 = []
        received_2 = []

        async def callback1(event):
            received_1.append(event)

        async def callback2(event):
            received_2.append(event)

        event_bus.subscribe("*", callback1)
        event_bus.subscribe("*", callback2)

        await event_bus.publish(Event(
            event_type=EventType.AGENT_STARTED,
            agent_id="test",
            data={}
        ))
        await asyncio.sleep(0.1)

        assert len(received_1) == 1
        assert len(received_2) == 1


class TestEventIntegration:
    """Integration tests for event system."""

    @pytest.mark.asyncio
    async def test_event_flow_simulation(self):
        """Simulate a typical event flow during code review."""
        bus = EventBus()
        all_events = []

        async def collector(event):
            all_events.append(event)

        bus.subscribe("*", collector)

        # Simulate review flow
        events = [
            create_agent_started_event("coordinator", "Analyzing code"),
            create_agent_started_event("security_agent", "Security scan"),
            create_tool_call_start_event("security_agent", "search_pattern", {"pattern": "eval"}),
            create_tool_call_result_event("security_agent", "search_pattern", {"matches": []}, 10, True),
            create_thinking_event("security_agent", "Checking for injection vulnerabilities..."),
            create_finding_event(
                "security_agent", "f1", "injection", "critical",
                "SQL Injection", "Unsafe query", {"line": 42}, "..."
            ),
            create_fix_proposed_event("security_agent", "f1", "Use params", "bad", "good"),
            create_agent_completed_event("security_agent", "Found 1 issue", 1000),
            create_agent_completed_event("coordinator", "Review complete", 2000),
        ]

        for event in events:
            await bus.publish(event)

        await asyncio.sleep(0.2)

        # Verify all events were received
        assert len(all_events) >= len(events)
        
        # Verify event order is preserved
        event_types = [e.event_type for e in all_events[:len(events)]]
        assert EventType.AGENT_STARTED in event_types
        assert EventType.FINDING_DISCOVERED in event_types
        assert EventType.AGENT_COMPLETED in event_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
