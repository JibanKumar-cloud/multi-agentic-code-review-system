"""
Event type definitions for the multi-agent system.
Implements the schema defined in STREAMING_EVENTS_SPEC.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
import json


class EventType(Enum):
    """All event types supported by the system."""
    
    # Planning events
    PLAN_CREATED = "plan_created"
    PLAN_STEP_STARTED = "plan_step_started"
    PLAN_STEP_COMPLETED = "plan_step_completed"
    
    # Agent lifecycle events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    
    # Agent mode events
    MODE_CHANGED = "mode_changed"
    
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
    
    # System events
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"


class Severity(Enum):
    """Severity levels for findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(Enum):
    """Categories of findings."""
    SECURITY = "security"
    BUG = "bug"
    STYLE = "style"
    PERFORMANCE = "performance"


@dataclass
class Location:
    """Location of a finding in the code."""
    file: str
    line_start: int
    line_end: int
    code_snippet: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "code_snippet": self.code_snippet
        }


@dataclass
class Finding:
    """A code review finding."""
    finding_id: str
    step_id: str
    category: str
    agent_id: str
    severity: str
    finding_type: str
    title: str
    description: str
    location: Location
    confidence: float = 1.0

    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "step_id": self.step_id,
            "category": self.category,
            "agent_id": self.agent_id,
            "severity": self.severity,
            "type": self.finding_type,
            "title": self.title,
            "description": self.description,
            "location": self.location.to_dict(),
            "confidence": self.confidence
        }


@dataclass
class Fix:
    """A proposed fix for a finding."""
    fix_id: str
    finding_id: str
    agent_id: str
    original_code: str
    proposed_code: str
    explanation: str
    confidence: float = 0.8
    auto_applicable: bool = True
    verified: bool = False
    verification_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fix_id": self.fix_id,
            "finding_id": self.finding_id,
            "agent_id": self.agent_id,
            "original_code": self.original_code,
            "proposed_code": self.proposed_code,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "auto_applicable": self.auto_applicable,
            "verified": self.verified,
            "verification_result": self.verification_result
        }


@dataclass
class PlanStep:
    """A step in the execution plan."""
    step_id: str
    description: str
    agent: str
    parallel: bool = False
    status: str = "pending"  # pending, running, completed, failed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "agent": self.agent,
            "parallel": self.parallel,
            "status": self.status
        }


@dataclass
class Event:
    """Base event structure for the system."""
    
    event_type: EventType
    agent_id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    
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
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())
    
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


# ============================================================================
# Event Factory Functions
# ============================================================================

def create_review_started_event(review_id: str, filename: str, code_lines: int) -> Event:
    """Create a review_started event."""
    return Event(
        event_type=EventType.REVIEW_STARTED,
        agent_id="system",
        data={
            "review_id": review_id,
            "filename": filename,
            "code_lines": code_lines
        }
    )


def create_plan_created_event(
    plan_id: str,
    steps: List[PlanStep],
    estimated_duration_ms: Optional[int] = None
) -> Event:
    """Create a plan_created event."""
    return Event(
        event_type=EventType.PLAN_CREATED,
        agent_id="coordinator",
        data={
            "plan_id": plan_id,
            "steps": [s.to_dict() for s in steps],
            "estimated_duration_ms": estimated_duration_ms
        }
    )


def create_plan_step_started_event(plan_id: str, step_id: str, agent: str) -> Event:
    """Create a plan_step_started event."""
    return Event(
        event_type=EventType.PLAN_STEP_STARTED,
        agent_id="coordinator",
        data={
            "plan_id": plan_id,
            "step_id": step_id,
            "agent": agent
        }
    )


def create_plan_step_completed_event(
    plan_id: str,
    step_id: str,
    agent: str,
    success: bool,
    duration_ms: int
) -> Event:
    """Create a plan_step_completed event."""
    return Event(
        event_type=EventType.PLAN_STEP_COMPLETED,
        agent_id="coordinator",
        data={
            "plan_id": plan_id,
            "step_id": step_id,
            "agent": agent,
            "success": success,
            "duration_ms": duration_ms
        }
    )


def create_agent_started_event(
    agent_id: str,
    task: str,
    input_summary: str = ""
) -> Event:
    """Create an agent_started event."""
    return Event(
        event_type=EventType.AGENT_STARTED,
        agent_id=agent_id,
        data={
            "task": task,
            "input_summary": input_summary
        }
    )


def create_agent_completed_event(
    agent_id: str,
    success: bool,
    findings_count: int,
    fixes_proposed: int,
    duration_ms: int,
    summary: str
) -> Event:
    """Create an agent_completed event."""
    return Event(
        event_type=EventType.AGENT_COMPLETED,
        agent_id=agent_id,
        data={
            "success": success,
            "findings_count": findings_count,
            "fixes_proposed": fixes_proposed,
            "duration_ms": duration_ms,
            "summary": summary
        }
    )


def create_agent_error_event(
    agent_id: str,
    error_type: str,
    message: str,
    recoverable: bool = True,
    will_retry: bool = False,
    attempt: int = 0,
    max_attempts: int = 0,
    delay_s: int = 0

) -> Event:
    """Create an agent_error event."""

    return Event(
        event_type=EventType.AGENT_ERROR,
        agent_id=agent_id,
        data={
            "error_type": error_type,
            "message": message,
            "recoverable": recoverable,
            "will_retry": will_retry,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "delay_s": delay_s

        }
    )


def create_thinking_event(agent_id: str, chunk: str) -> Event:
    """Create a thinking event."""
    return Event(
        event_type=EventType.THINKING,
        agent_id=agent_id,
        data={"chunk": chunk}
    )


def create_mode_changed_event(agent_id: str, mode: str) -> Event:
    """Create a mode_changed event.
    
    Args:
        agent_id: The agent that changed mode
        mode: Either 'thinking' or 'streaming'
    """
    return Event(
        event_type=EventType.MODE_CHANGED,
        agent_id=agent_id,
        data={"mode": mode}
    )


def create_thinking_complete_event(
    agent_id: str,
    full_thinking: Optional[str] = None,
    duration_ms: int = 0
) -> Event:
    """Create a thinking_complete event."""
    return Event(
        event_type=EventType.THINKING_COMPLETE,
        agent_id=agent_id,
        data={
            "full_thinking": full_thinking,
            "duration_ms": duration_ms
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
    duration_ms: int,
    error: Optional[str] = None
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
            "error": error,
            "duration_ms": duration_ms
        }
    )


def create_finding_discovered_event(
    agent_id: str,
    finding: Finding
) -> Event:
    """Create a finding_discovered event."""
    return Event(
        event_type=EventType.FINDING_DISCOVERED,
        agent_id=agent_id,
        data=finding.to_dict()
    )


def create_fix_proposed_event(
    agent_id: str,
    fix: Fix
) -> Event:
    """Create a fix_proposed event."""
    return Event(
        event_type=EventType.FIX_PROPOSED,
        agent_id=agent_id,
        data=fix.to_dict()
    )


def create_fix_verified_event(
    agent_id: str,
    fix_id: str,
    finding_id: str,
    verification_passed: bool,
    verification_method: str,
    test_output: str,
    duration_ms: int
) -> Event:
    """Create a fix_verified event."""
    return Event(
        event_type=EventType.FIX_VERIFIED,
        agent_id=agent_id,
        data={
            "fix_id": fix_id,
            "finding_id": finding_id,
            "verification_passed": verification_passed,
            "verification_method": verification_method,
            "test_output": test_output,
            "duration_ms": duration_ms
        }
    )


def create_findings_consolidated_event(
    total_findings: int,
    by_severity: Dict[str, int],
    by_category: Dict[str, int],
    duplicates_removed: int
) -> Event:
    """Create a findings_consolidated event."""
    return Event(
        event_type=EventType.FINDINGS_CONSOLIDATED,
        agent_id="coordinator",
        data={
            "total_findings": total_findings,
            "by_severity": by_severity,
            "by_category": by_category,
            "duplicates_removed": duplicates_removed
        }
    )


def create_final_report_event(
    review_id: str,
    status: str,
    summary: str,
    findings: List[Dict[str, Any]],
    fixes: List[Dict[str, Any]],
    metrics: Dict[str, Any]
) -> Event:
    """Create a final_report event."""
    return Event(
        event_type=EventType.FINAL_REPORT,
        agent_id="coordinator",
        data={
            "review_id": review_id,
            "status": status,
            "summary": summary,
            "findings": findings,
            "fixes": fixes,
            "metrics": metrics
        }
    )
