"""
Event type definitions for the multi-agent system.

See STREAMING_EVENTS_SPEC.md for full event schema documentation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class EventType(Enum):
    """Types of events in the system."""

    # Planning events
    PLAN_CREATED = "plan_created"
    PLAN_STEP_STARTED = "plan_step_started"
    PLAN_STEP_COMPLETED = "plan_step_completed"

    # Agent lifecycle events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"

    # Thinking/reasoning events
    THINKING = "thinking"
    THINKING_COMPLETE = "thinking_complete"

    # Tool events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"

    # Finding events
    FINDING_DISCOVERED = "finding_discovered"
    FIX_PROPOSED = "fix_proposed"
    FIX_VERIFIED = "fix_verified"

    # Communication events
    AGENT_MESSAGE = "agent_message"
    FINDINGS_CONSOLIDATED = "findings_consolidated"
    FINAL_REPORT = "final_report"


@dataclass
class Event:
    """
    Base event structure for the system.

    All events follow this structure for consistency and
    easy serialization for streaming.
    """

    event_type: EventType
    agent_id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None  # For linking related events

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "correlation_id": self.correlation_id,
            "data": self.data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=EventType(data["event_type"]),
            agent_id=data["agent_id"],
            timestamp=datetime.fromisoformat(data["timestamp"].rstrip("Z")),
            correlation_id=data.get("correlation_id"),
            data=data.get("data", {})
        )


# Convenience factory functions for common events
def create_agent_started_event(agent_id: str, agent_type: str, task: str) -> Event:
    """Create an agent_started event."""
    return Event(
        event_type=EventType.AGENT_STARTED,
        agent_id=agent_id,
        data={
            "agent_type": agent_type,
            "task": task,
            "status": "running"
        }
    )


def create_thinking_event(agent_id: str, chunk: str, is_complete: bool = False) -> Event:
    """Create a thinking event."""
    return Event(
        event_type=EventType.THINKING_COMPLETE if is_complete else EventType.THINKING,
        agent_id=agent_id,
        data={
            "chunk": chunk if not is_complete else None,
            "full_thinking": chunk if is_complete else None
        }
    )


def create_finding_event(
    agent_id: str,
    finding_id: str,
    finding_type: str,
    severity: str,
    title: str,
    description: str,
    location: Dict[str, Any],
    confidence: float = 1.0
) -> Event:
    """Create a finding_discovered event."""
    return Event(
        event_type=EventType.FINDING_DISCOVERED,
        agent_id=agent_id,
        data={
            "finding_id": finding_id,
            "type": finding_type,
            "severity": severity,
            "title": title,
            "description": description,
            "location": location,
            "confidence": confidence
        }
    )


def create_tool_call_start_event(
    agent_id: str,
    tool_call_id: str,
    tool_name: str,
    input_data: Dict[str, Any],
    purpose: str = ""
) -> Event:
    """Create a tool_call_start event."""
    return Event(
        event_type=EventType.TOOL_CALL_START,
        agent_id=agent_id,
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "input": input_data,
            "purpose": purpose
        }
    )


def create_tool_call_result_event(
    agent_id: str,
    tool_call_id: str,
    tool_name: str,
    success: bool,
    output: Any,
    duration_ms: int
) -> Event:
    """Create a tool_call_result event."""
    return Event(
        event_type=EventType.TOOL_CALL_RESULT,
        agent_id=agent_id,
        data={
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "success": success,
            "output": output,
            "duration_ms": duration_ms
        }
    )
