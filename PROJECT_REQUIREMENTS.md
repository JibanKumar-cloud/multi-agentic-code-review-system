# Project Requirements

## Multi-Agent Code Review System with Real-Time Observability

This document contains detailed technical specifications for the assessment.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Agent Architecture](#agent-architecture)
3. [Event Streaming System](#event-streaming-system)
4. [Streaming UI](#streaming-ui)
5. [Autonomous Debugging](#autonomous-debugging)
6. [Test Harness](#test-harness)
7. [Technical Constraints](#technical-constraints)
8. [Bonus Features](#bonus-features)

---

## System Overview

### What You're Building

A system that takes Python code as input and produces:
1. **Security analysis** - vulnerabilities, injection risks, hardcoded secrets
2. **Bug detection** - logic errors, null references, type issues, edge cases
3. **Proposed fixes** - for issues that can be automatically corrected
4. **Real-time visibility** - streaming UI showing all agent activity

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                   │
│                         (Python code to review)                          │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          COORDINATOR AGENT                                │
│  • Analyzes code structure                                               │
│  • Creates review plan                                                   │
│  • Delegates to specialist agents                                        │
│  • Consolidates findings                                                 │
│  • Resolves conflicts between agents                                     │
└───────────┬─────────────────────┬─────────────────────┬──────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│  SECURITY AGENT   │ │  BUG DETECTION    │ │  (OPTIONAL)       │
│                   │ │  AGENT            │ │  Additional Agent │
│  • SQL injection  │ │  • Null refs      │ │  • Style          │
│  • XSS            │ │  • Logic errors   │ │  • Performance    │
│  • Hardcoded keys │ │  • Type issues    │ │  • etc.           │
│  • Auth flaws     │ │  • Race conditions│ │                   │
└─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           EVENT BUS                                       │
│  All agent activity published as streaming events                        │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         WEBSOCKET/SSE API                                 │
│  Real-time event stream to connected clients                             │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          STREAMING UI                                     │
│  • Agent status cards                                                    │
│  • Live thought streams                                                  │
│  • Tool invocation logs                                                  │
│  • Findings feed                                                         │
│  • Plan visualization                                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

### Required Agents

#### 1. Coordinator Agent

**Responsibilities:**
- Receive code input and analyze its structure
- Create an execution plan (which agents to invoke, in what order)
- Delegate tasks to specialist agents
- Collect and consolidate findings from all agents
- Resolve conflicting findings (if any)
- Produce final review report

**Must emit these events:**
- `plan_created` - when execution plan is ready
- `agent_delegated` - when assigning work to specialist
- `findings_consolidated` - when merging all results
- `final_report` - when review is complete

#### 2. Security Agent

**Responsibilities:**
- Scan for security vulnerabilities
- Identify injection risks (SQL, command, etc.)
- Find hardcoded secrets/credentials
- Detect authentication/authorization flaws
- Check for unsafe deserialization
- Identify XSS vulnerabilities

**Must emit these events:**
- `agent_started` - when beginning analysis
- `thinking` (streaming) - reasoning process
- `tool_call_start` / `tool_call_result` - if using tools
- `finding_discovered` - for each issue found
- `agent_completed` - when done

#### 3. Bug Detection Agent

**Responsibilities:**
- Find potential null/None reference errors
- Identify logic errors and off-by-one bugs
- Detect type mismatches and coercion issues
- Find potential race conditions
- Identify resource leaks
- Check error handling gaps

**Must emit same event types as Security Agent.**

### Agent Communication

Agents communicate through the Coordinator. Direct agent-to-agent communication is optional but can be implemented for bonus points.

**Shared Context:**
All agents should have access to:
- The original code being reviewed
- Metadata (filename, language, etc.)
- Findings from other agents (for conflict resolution)

### Agent Interface

Each agent should implement this interface (or equivalent):

```python
class BaseAgent:
    """Base interface for all review agents."""

    async def analyze(
        self,
        code: str,
        context: dict,
        event_callback: Callable[[AgentEvent], None]
    ) -> AgentResult:
        """
        Analyze code and emit events during processing.

        Args:
            code: The Python code to analyze
            context: Shared context (metadata, other findings)
            event_callback: Function to call for each event

        Returns:
            AgentResult with findings and metadata
        """
        raise NotImplementedError
```

---

## Event Streaming System

### Requirements

1. **Real-time delivery** - Events must stream as they happen, not batch
2. **Ordered** - Events must arrive in order per agent
3. **Concurrent** - Multiple agents can emit events simultaneously
4. **Reliable** - No dropped events under normal operation

### Implementation Options

#### Option A: WebSocket (Recommended)

```python
# FastAPI WebSocket endpoint
@app.websocket("/ws/review")
async def review_websocket(websocket: WebSocket):
    await websocket.accept()

    # Subscribe to event bus
    async for event in event_bus.subscribe():
        await websocket.send_json(event.to_dict())
```

#### Option B: Server-Sent Events

```python
# FastAPI SSE endpoint
@app.get("/stream/review")
async def review_stream(request: Request):
    async def event_generator():
        async for event in event_bus.subscribe():
            yield f"data: {json.dumps(event.to_dict())}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Event Schema

See `STREAMING_EVENTS_SPEC.md` for complete event type definitions.

All events must include:
- `event_type` - The type of event
- `agent_id` - Which agent emitted it
- `timestamp` - ISO 8601 timestamp
- `data` - Event-specific payload

---

## Streaming UI

### Required Elements

Your UI must display these in real-time:

#### 1. Agent Status Panel

Show all agents and their current state:
- `idle` - Not yet started
- `thinking` - Processing/reasoning
- `tool_calling` - Invoking a tool
- `completed` - Finished
- `error` - Failed

```
┌─────────────────────────────────────────────┐
│ AGENTS                                      │
├─────────────────────────────────────────────┤
│ ● Coordinator      [THINKING]               │
│ ● Security Agent   [TOOL_CALLING]           │
│ ○ Bug Agent        [IDLE]                   │
└─────────────────────────────────────────────┘
```

#### 2. Live Thought Stream

Stream agent reasoning as it happens (like extended thinking):

```
┌─────────────────────────────────────────────┐
│ SECURITY AGENT - Thinking                   │
├─────────────────────────────────────────────┤
│ Analyzing the database query on line 45...  │
│ I see string concatenation being used to    │
│ build the SQL query. This is a classic      │
│ pattern for SQL injection vulnerabilities.  │
│ Let me check if user input flows into...█   │
└─────────────────────────────────────────────┘
```

#### 3. Tool Activity Log

Show every tool invocation with inputs and outputs:

```
┌─────────────────────────────────────────────┐
│ TOOL CALLS                                  │
├─────────────────────────────────────────────┤
│ 14:23:45 [SecurityAgent] code_executor      │
│   Input: {"code": "test_sql_injection()"}   │
│   Output: "Vulnerability confirmed"         │
│   Duration: 234ms                           │
│                                             │
│ 14:23:42 [BugAgent] ast_parser              │
│   Input: {"file": "main.py"}                │
│   Output: {"functions": 12, "classes": 3}   │
│   Duration: 45ms                            │
└─────────────────────────────────────────────┘
```

#### 4. Findings Feed

Display issues as they're discovered:

```
┌─────────────────────────────────────────────┐
│ FINDINGS                                    │
├─────────────────────────────────────────────┤
│ 🔴 CRITICAL - SQL Injection (line 45)       │
│    User input directly concatenated into    │
│    SQL query without sanitization           │
│    [View Details] [View Fix]                │
│                                             │
│ 🟡 MEDIUM - Potential None reference (ln 23)│
│    Variable 'user' may be None when...      │
│    [View Details] [View Fix]                │
└─────────────────────────────────────────────┘
```

#### 5. Execution Plan

Show what the Coordinator decided:

```
┌─────────────────────────────────────────────┐
│ EXECUTION PLAN                              │
├─────────────────────────────────────────────┤
│ 1. ✓ Parse code structure                   │
│ 2. ✓ Security analysis (parallel)          │
│ 3. → Bug detection (in progress)           │
│ 4. ○ Consolidate findings                   │
│ 5. ○ Generate fixes                         │
│ 6. ○ Final report                           │
└─────────────────────────────────────────────┘
```

### UI Implementation

You choose the technology:

| Option | Pros | Cons |
|--------|------|------|
| **Web (React)** | Rich UI, familiar | More setup |
| **Web (Vanilla JS)** | Simple, no build | Less structured |
| **Terminal (Rich)** | Fast, no frontend | Limited interactivity |
| **Desktop (Electron)** | Native feel | Overkill for this |

**Minimum requirement:** Real-time streaming updates. No polling. No page refreshes.

---

## Autonomous Debugging

### Fix Proposal

When an agent finds an issue, it should (when possible):

1. **Propose a fix** - Generate corrected code
2. **Explain the fix** - Why this change resolves the issue
3. **Verify the fix** - Test that it works (if testable)

### Required Events

```python
# When proposing a fix
{
    "event_type": "fix_proposed",
    "agent_id": "security_agent",
    "data": {
        "finding_id": "sqli_001",
        "original_code": "query = f'SELECT * FROM users WHERE id = {user_id}'",
        "proposed_fix": "query = 'SELECT * FROM users WHERE id = ?'\ncursor.execute(query, (user_id,))",
        "explanation": "Use parameterized queries to prevent SQL injection",
        "confidence": 0.95
    }
}

# When verifying a fix
{
    "event_type": "fix_verified",
    "agent_id": "security_agent",
    "data": {
        "finding_id": "sqli_001",
        "verification_passed": true,
        "test_output": "Parameterized query executed successfully",
        "duration_ms": 156
    }
}
```

### Verification (When Possible)

For some fixes, you can verify they work:

- **Syntax check** - Does the fixed code parse?
- **Type check** - Does it pass basic type validation?
- **Unit test** - If tests exist, do they still pass?
- **Targeted test** - Run a specific test for the vulnerability

If verification isn't possible, emit `fix_proposed` without `fix_verified`.

---

## Test Harness

### Provided Test Cases

The `test_cases/buggy_samples/` directory contains Python files with known issues:

| File | Issues |
|------|--------|
| `sql_injection.py` | SQL injection vulnerability |
| `null_reference.py` | Potential None dereference |
| `hardcoded_secret.py` | API key in source code |
| `race_condition.py` | Thread safety issue |
| `xss_vulnerability.py` | Cross-site scripting |
| `type_coercion.py` | Implicit type conversion bug |
| `resource_leak.py` | Unclosed file handle |
| `auth_bypass.py` | Authentication flaw |
| `logic_error.py` | Off-by-one / boundary bug |
| `error_swallowing.py` | Caught and ignored exception |

### Expected Output

`test_cases/expected_findings.json` contains ground truth:

```json
{
  "sql_injection.py": {
    "findings": [
      {
        "type": "security",
        "severity": "critical",
        "category": "sql_injection",
        "line": 45,
        "description": "User input concatenated into SQL query"
      }
    ]
  }
}
```

### Evaluation Metrics

Run your system against all test cases and report:

| Metric | Formula | Target |
|--------|---------|--------|
| **Precision** | True Positives / (TP + False Positives) | > 0.7 |
| **Recall** | True Positives / (TP + False Negatives) | > 0.7 |
| **F1 Score** | 2 * (Precision * Recall) / (P + R) | > 0.7 |
| **Fix Success Rate** | Verified Fixes / Proposed Fixes | > 0.5 |

### Running Evaluation

```bash
# Run your system against test cases
python evaluate.py --input test_cases/buggy_samples/ --expected test_cases/expected_findings.json

# Output: metrics.json with precision, recall, F1, fix rate
```

You must create `evaluate.py` as part of your submission.

---

## Technical Constraints

### Required

| Constraint | Requirement |
|------------|-------------|
| Language | Python 3.11+ |
| LLM | Anthropic Claude API (claude-sonnet-4-20250514 recommended) |
| Streaming | WebSocket or SSE (no polling) |
| Events | Must conform to `STREAMING_EVENTS_SPEC.md` |
| Agents | Minimum 3 (Coordinator + 2 specialists) |

### API Key

- Will be provided separately
- Store in `.env` file (add to `.gitignore`)
- Has usage limits - be mindful of tokens
- Will be deactivated after deadline

### Dependencies

Recommended (not required):
```
anthropic>=0.39.0
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=11.0
python-dotenv>=1.0.0
pydantic>=2.0.0
rich>=13.0.0  # If using terminal UI
```

---

## Bonus Features

### Tier 1 Bonuses (+5 points each)

| Feature | Description |
|---------|-------------|
| **RAG System** | Retrieval over Python docs for better analysis |
| **MCP Server** | Custom MCP tool for code execution |
| **AWS Design Doc** | Architecture for Lambda/API Gateway deployment |
| **Polished Web UI** | Professional, well-designed interface |
| **High Fix Rate** | >70% of proposed fixes verify successfully |

### Tier 2 Bonuses (+3 points each)

| Feature | Description |
|---------|-------------|
| **Additional Agent** | Style checker, performance analyzer, etc. |
| **Agent-to-Agent Communication** | Direct messages between specialists |
| **Conversation History** | Multi-turn review sessions |

### Tier 3 Bonuses (+2 points each)

| Feature | Description |
|---------|-------------|
| **Cost Optimization** | Token usage tracking and analysis |
| **Caching** | Cache repeated analysis patterns |
| **Configuration UI** | Let users configure agent behavior |

---

## Submission Checklist

Before submitting, verify:

- [ ] All code pushed to GitHub
- [ ] Runs from fresh clone with documented setup
- [ ] All three agents working (Coordinator + 2 specialists)
- [ ] Events streaming to UI in real-time
- [ ] UI shows agent states, thoughts, tool calls, findings
- [ ] Test harness runs and produces metrics
- [ ] `TIME_ESTIMATION.md` complete (initial + actual)
- [ ] `BLOCKERS_AND_SOLUTIONS.md` documents challenges
- [ ] `presentation_outline.md` prepared
- [ ] README has clear setup and architecture docs
- [ ] No API keys in repository

---

## Timeline Guidance

| Phase | Recommended Time |
|-------|------------------|
| Read all docs, plan architecture | 2-3 hours |
| Basic agent + Claude integration | 2-3 hours |
| Event streaming infrastructure | 2-3 hours |
| Coordinator + specialist agents | 4-6 hours |
| Streaming UI | 3-5 hours |
| Autonomous fix proposals | 2-3 hours |
| Test harness + evaluation | 2-3 hours |
| Documentation + polish | 2-3 hours |

**Total: 19-29 hours** (varies by experience)

---

## Questions?

Clarifying questions about requirements are welcome. We won't provide implementation hints, but we'll clarify scope and expectations.

Good luck!
