# Streaming Events Specification

This document defines the event schema that your system **must** implement. All events must conform to these specifications.

---

## Base Event Structure

Every event must include these fields:

```python
{
    "event_type": str,      # One of the defined event types
    "agent_id": str,        # Unique identifier for the agent
    "timestamp": str,       # ISO 8601 format (e.g., "2024-01-15T14:23:45.123Z")
    "data": dict            # Event-specific payload
}
```

### Example

```json
{
    "event_type": "thinking",
    "agent_id": "security_agent",
    "timestamp": "2024-01-15T14:23:45.123Z",
    "data": {
        "chunk": "Analyzing the input validation on line 23..."
    }
}
```

---

## Event Types

### 1. Plan Events

#### `plan_created`

Emitted by Coordinator when execution plan is ready.

```python
{
    "event_type": "plan_created",
    "agent_id": "coordinator",
    "timestamp": "...",
    "data": {
        "plan_id": str,              # Unique plan identifier
        "steps": [                   # Ordered list of steps
            {
                "step_id": str,
                "description": str,
                "agent": str,        # Agent responsible
                "parallel": bool     # Can run in parallel with others
            }
        ],
        "estimated_duration_ms": int  # Optional estimate
    }
}
```

#### `plan_step_started`

Emitted when a plan step begins.

```python
{
    "event_type": "plan_step_started",
    "agent_id": "coordinator",
    "timestamp": "...",
    "data": {
        "plan_id": str,
        "step_id": str,
        "agent": str
    }
}
```

#### `plan_step_completed`

Emitted when a plan step finishes.

```python
{
    "event_type": "plan_step_completed",
    "agent_id": "coordinator",
    "timestamp": "...",
    "data": {
        "plan_id": str,
        "step_id": str,
        "agent": str,
        "success": bool,
        "duration_ms": int
    }
}
```

---

### 2. Agent Lifecycle Events

#### `agent_started`

Emitted when an agent begins work.

```python
{
    "event_type": "agent_started",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "task": str,                 # Description of what agent will do
        "input_summary": str         # Brief summary of input (e.g., "245 lines of Python")
    }
}
```

#### `agent_completed`

Emitted when an agent finishes.

```python
{
    "event_type": "agent_completed",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "success": bool,
        "findings_count": int,
        "fixes_proposed": int,
        "duration_ms": int,
        "summary": str               # Brief summary of results
    }
}
```

#### `agent_error`

Emitted when an agent encounters an error.

```python
{
    "event_type": "agent_error",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "error_type": str,           # e.g., "api_error", "timeout", "parse_error"
        "message": str,
        "recoverable": bool,
        "will_retry": bool
    }
}
```

---

### 3. Thinking Events

#### `thinking`

Emitted as the agent reasons (streaming chunks).

```python
{
    "event_type": "thinking",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "chunk": str                 # Text chunk of reasoning
    }
}
```

**Important:** This should stream incrementally, not wait for complete thoughts.

#### `thinking_complete`

Emitted when thinking phase is done.

```python
{
    "event_type": "thinking_complete",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "full_thinking": str,        # Complete thinking text (optional)
        "duration_ms": int
    }
}
```

---

### 4. Tool Events

#### `tool_call_start`

Emitted when agent is about to invoke a tool.

```python
{
    "event_type": "tool_call_start",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "tool_call_id": str,         # Unique ID for this call
        "tool_name": str,            # Name of the tool
        "input": dict,               # Tool input parameters
        "purpose": str               # Why the agent is calling this tool
    }
}
```

#### `tool_call_result`

Emitted when tool returns.

```python
{
    "event_type": "tool_call_result",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "tool_call_id": str,
        "tool_name": str,
        "success": bool,
        "output": any,               # Tool output (truncate if very large)
        "error": str | null,         # Error message if failed
        "duration_ms": int
    }
}
```

---

### 5. Finding Events

#### `finding_discovered`

Emitted when agent identifies an issue.

```python
{
    "event_type": "finding_discovered",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "finding_id": str,           # Unique ID for this finding
        "category": str,             # e.g., "security", "bug", "style"
        "severity": str,             # "critical", "high", "medium", "low", "info"
        "type": str,                 # e.g., "sql_injection", "null_reference"
        "title": str,                # Short title
        "description": str,          # Detailed description
        "location": {
            "file": str,
            "line_start": int,
            "line_end": int,
            "code_snippet": str      # The problematic code
        },
        "confidence": float          # 0.0 to 1.0
    }
}
```

---

### 6. Fix Events

#### `fix_proposed`

Emitted when agent proposes a fix.

```python
{
    "event_type": "fix_proposed",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "fix_id": str,
        "finding_id": str,           # Links to the finding
        "original_code": str,
        "proposed_code": str,
        "explanation": str,          # Why this fix works
        "confidence": float,
        "auto_applicable": bool      # Can be applied automatically
    }
}
```

#### `fix_verified`

Emitted after testing a proposed fix.

```python
{
    "event_type": "fix_verified",
    "agent_id": str,
    "timestamp": "...",
    "data": {
        "fix_id": str,
        "finding_id": str,
        "verification_passed": bool,
        "verification_method": str,  # e.g., "syntax_check", "unit_test", "type_check"
        "test_output": str,
        "duration_ms": int
    }
}
```

---

### 7. Communication Events

#### `agent_message`

Emitted for inter-agent communication (optional, for bonus).

```python
{
    "event_type": "agent_message",
    "agent_id": str,                 # Sender
    "timestamp": "...",
    "data": {
        "to": str,                   # Recipient agent
        "message_type": str,         # e.g., "request", "response", "notification"
        "content": dict              # Message content
    }
}
```

---

### 8. Report Events

#### `findings_consolidated`

Emitted when Coordinator merges all findings.

```python
{
    "event_type": "findings_consolidated",
    "agent_id": "coordinator",
    "timestamp": "...",
    "data": {
        "total_findings": int,
        "by_severity": {
            "critical": int,
            "high": int,
            "medium": int,
            "low": int,
            "info": int
        },
        "by_category": {
            "security": int,
            "bug": int,
            "style": int
        },
        "duplicates_removed": int
    }
}
```

#### `final_report`

Emitted when review is complete.

```python
{
    "event_type": "final_report",
    "agent_id": "coordinator",
    "timestamp": "...",
    "data": {
        "review_id": str,
        "status": str,               # "completed", "partial", "failed"
        "summary": str,              # Executive summary
        "findings": [...],           # All findings
        "fixes": [...],              # All proposed fixes
        "metrics": {
            "total_lines_analyzed": int,
            "total_findings": int,
            "fixes_proposed": int,
            "fixes_verified": int,
            "duration_ms": int
        }
    }
}
```

---

## Event Ordering

Events should be emitted in logical order:

```
plan_created
├── plan_step_started (Security)
│   ├── agent_started
│   ├── thinking (multiple)
│   ├── thinking_complete
│   ├── tool_call_start
│   ├── tool_call_result
│   ├── finding_discovered
│   ├── fix_proposed
│   ├── fix_verified
│   ├── agent_completed
│   └── plan_step_completed
├── plan_step_started (Bug Detection) [may be parallel]
│   └── ...
├── findings_consolidated
└── final_report
```

---

## Streaming Requirements

### Real-Time Delivery

- Events must be sent as they occur, not batched
- `thinking` events should stream character-by-character or in small chunks
- Maximum latency: 100ms from event occurrence to WebSocket delivery

### Concurrency

- Multiple agents may emit events simultaneously
- Events from different agents may interleave
- Each agent's events must be internally ordered

### Connection Handling

- Support multiple simultaneous UI connections
- Handle client disconnection gracefully
- Consider reconnection scenarios (optional: event replay)

---

## Python Type Definitions

For reference, here are Pydantic models:

```python
from pydantic import BaseModel
from typing import Literal, Optional, Any
from datetime import datetime

class Location(BaseModel):
    file: str
    line_start: int
    line_end: int
    code_snippet: str

class Finding(BaseModel):
    finding_id: str
    category: Literal["security", "bug", "style", "performance"]
    severity: Literal["critical", "high", "medium", "low", "info"]
    type: str
    title: str
    description: str
    location: Location
    confidence: float

class PlanStep(BaseModel):
    step_id: str
    description: str
    agent: str
    parallel: bool = False

class AgentEvent(BaseModel):
    event_type: str
    agent_id: str
    timestamp: datetime
    data: dict

# Event type literals
EventType = Literal[
    "plan_created",
    "plan_step_started",
    "plan_step_completed",
    "agent_started",
    "agent_completed",
    "agent_error",
    "thinking",
    "thinking_complete",
    "tool_call_start",
    "tool_call_result",
    "finding_discovered",
    "fix_proposed",
    "fix_verified",
    "agent_message",
    "findings_consolidated",
    "final_report"
]
```

---

## Validation

Your system should validate that:

1. All emitted events conform to this schema
2. Required fields are present
3. Timestamps are valid ISO 8601
4. Event types are from the defined list
5. References (finding_id, fix_id) are consistent

Consider adding a debug mode that validates all events before emission.

---

## Example Event Sequence

Here's a complete example of events for a simple review:

```json
{"event_type": "plan_created", "agent_id": "coordinator", "timestamp": "2024-01-15T14:00:00.000Z", "data": {"plan_id": "plan_001", "steps": [{"step_id": "s1", "description": "Security scan", "agent": "security_agent", "parallel": true}, {"step_id": "s2", "description": "Bug detection", "agent": "bug_agent", "parallel": true}]}}

{"event_type": "plan_step_started", "agent_id": "coordinator", "timestamp": "2024-01-15T14:00:00.100Z", "data": {"plan_id": "plan_001", "step_id": "s1", "agent": "security_agent"}}

{"event_type": "agent_started", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:00.150Z", "data": {"task": "Scan for security vulnerabilities", "input_summary": "main.py - 150 lines"}}

{"event_type": "thinking", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:01.000Z", "data": {"chunk": "Analyzing the code structure... "}}

{"event_type": "thinking", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:01.500Z", "data": {"chunk": "I see a database query on line 45. "}}

{"event_type": "thinking", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:02.000Z", "data": {"chunk": "This appears to use string concatenation for user input."}}

{"event_type": "thinking_complete", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:02.100Z", "data": {"duration_ms": 2000}}

{"event_type": "finding_discovered", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:02.200Z", "data": {"finding_id": "f001", "category": "security", "severity": "critical", "type": "sql_injection", "title": "SQL Injection Vulnerability", "description": "User input is concatenated directly into SQL query", "location": {"file": "main.py", "line_start": 45, "line_end": 45, "code_snippet": "query = f\"SELECT * FROM users WHERE id = {user_id}\""}, "confidence": 0.95}}

{"event_type": "fix_proposed", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:03.000Z", "data": {"fix_id": "fix001", "finding_id": "f001", "original_code": "query = f\"SELECT * FROM users WHERE id = {user_id}\"", "proposed_code": "query = \"SELECT * FROM users WHERE id = ?\"\ncursor.execute(query, (user_id,))", "explanation": "Use parameterized queries to prevent SQL injection", "confidence": 0.9, "auto_applicable": true}}

{"event_type": "agent_completed", "agent_id": "security_agent", "timestamp": "2024-01-15T14:00:03.500Z", "data": {"success": true, "findings_count": 1, "fixes_proposed": 1, "duration_ms": 3350, "summary": "Found 1 critical security issue"}}

{"event_type": "final_report", "agent_id": "coordinator", "timestamp": "2024-01-15T14:00:05.000Z", "data": {"review_id": "review_001", "status": "completed", "summary": "Code review complete. Found 1 critical security vulnerability.", "findings": [...], "fixes": [...], "metrics": {"total_lines_analyzed": 150, "total_findings": 1, "fixes_proposed": 1, "fixes_verified": 0, "duration_ms": 5000}}}
```

---

## Questions?

If anything in this spec is unclear, ask before implementing. The event schema is a hard requirement - your system must emit conforming events.
