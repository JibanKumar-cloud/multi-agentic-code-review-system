# Multi-Agent Design Patterns Reference

This document provides guidance on designing multi-agent systems for this assessment.

---

## Table of Contents

1. [Agent Architecture Patterns](#agent-architecture-patterns)
2. [Coordination Patterns](#coordination-patterns)
3. [Communication Patterns](#communication-patterns)
4. [Shared Memory Patterns](#shared-memory-patterns)
5. [Error Handling Patterns](#error-handling-patterns)
6. [Event Bus Implementation](#event-bus-implementation)

---

## Agent Architecture Patterns

### Pattern 1: Coordinator-Worker (Recommended)

A central coordinator delegates work to specialist workers.

```
                    ┌─────────────┐
                    │ Coordinator │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Worker A │    │ Worker B │    │ Worker C │
    └──────────┘    └──────────┘    └──────────┘
```

**Pros:**
- Clear hierarchy and responsibility
- Easy to add new workers
- Coordinator handles complexity

**Cons:**
- Coordinator can be bottleneck
- Single point of failure

**Implementation:**

```python
class Coordinator:
    def __init__(self, workers: list[BaseAgent]):
        self.workers = {w.agent_id: w for w in workers}

    async def execute_review(self, code: str, event_callback) -> ReviewResult:
        # 1. Create plan
        plan = self._create_plan(code)
        event_callback(plan_created_event(plan))

        # 2. Execute workers (parallel or sequential)
        results = await self._execute_workers(code, plan, event_callback)

        # 3. Consolidate findings
        consolidated = self._consolidate(results)
        event_callback(findings_consolidated_event(consolidated))

        # 4. Generate report
        report = self._generate_report(consolidated)
        event_callback(final_report_event(report))

        return report
```

---

### Pattern 2: Pipeline (Sequential)

Agents process in sequence, each building on the previous.

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Parser  │───▶│ Security│───▶│  Bugs   │───▶│ Report  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**Pros:**
- Simple to understand
- Each stage has clear input/output
- Easy debugging

**Cons:**
- No parallelism
- Slower overall

**Implementation:**

```python
class Pipeline:
    def __init__(self, stages: list[BaseAgent]):
        self.stages = stages

    async def execute(self, input_data, event_callback):
        context = {"original_input": input_data}

        for stage in self.stages:
            event_callback(agent_started_event(stage.agent_id))
            result = await stage.process(context, event_callback)
            context[stage.agent_id] = result
            event_callback(agent_completed_event(stage.agent_id, result))

        return context
```

---

### Pattern 3: Parallel Fan-Out/Fan-In

Multiple agents work simultaneously, results merged at the end.

```
                    ┌───────────────┐
                    │   Fan-Out     │
                    └───────┬───────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌──────────┐        ┌──────────┐        ┌──────────┐
  │ Agent A  │        │ Agent B  │        │ Agent C  │
  └────┬─────┘        └────┬─────┘        └────┬─────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                    ┌───────────────┐
                    │    Fan-In     │
                    └───────────────┘
```

**Pros:**
- Faster (parallel execution)
- Scales well

**Cons:**
- More complex coordination
- Need to handle partial failures

**Implementation:**

```python
import asyncio

class ParallelExecutor:
    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    async def execute(self, code: str, event_callback):
        # Fan-out: run all agents in parallel
        tasks = [
            asyncio.create_task(
                self._run_agent(agent, code, event_callback)
            )
            for agent in self.agents
        ]

        # Wait for all (with error handling)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Fan-in: merge results
        merged = self._merge_results(results)
        return merged

    async def _run_agent(self, agent, code, event_callback):
        event_callback(agent_started_event(agent.agent_id))
        try:
            result = await agent.analyze(code, event_callback)
            event_callback(agent_completed_event(agent.agent_id, result))
            return result
        except Exception as e:
            event_callback(agent_error_event(agent.agent_id, e))
            return None
```

---

## Coordination Patterns

### Plan-Based Coordination

Coordinator creates explicit plan before execution.

```python
@dataclass
class PlanStep:
    step_id: str
    agent: str
    description: str
    dependencies: list[str]  # step_ids that must complete first
    parallel: bool

class PlanBasedCoordinator:
    def _create_plan(self, code: str) -> list[PlanStep]:
        # Analyze code to determine what analysis is needed
        return [
            PlanStep("s1", "parser", "Parse AST", [], True),
            PlanStep("s2", "security", "Security scan", ["s1"], True),
            PlanStep("s3", "bugs", "Bug detection", ["s1"], True),
            PlanStep("s4", "consolidate", "Merge findings", ["s2", "s3"], False),
        ]

    async def execute_plan(self, plan: list[PlanStep], context, event_callback):
        completed = set()

        while len(completed) < len(plan):
            # Find steps ready to execute (dependencies satisfied)
            ready = [
                s for s in plan
                if s.step_id not in completed
                and all(d in completed for d in s.dependencies)
            ]

            # Execute ready steps (parallel if allowed)
            parallel_steps = [s for s in ready if s.parallel]
            if parallel_steps:
                await asyncio.gather(*[
                    self._execute_step(s, context, event_callback)
                    for s in parallel_steps
                ])
                completed.update(s.step_id for s in parallel_steps)
            elif ready:
                await self._execute_step(ready[0], context, event_callback)
                completed.add(ready[0].step_id)
```

---

### State Machine Coordination

Each agent reports state, coordinator transitions system.

```python
from enum import Enum

class AgentState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    COMPLETED = "completed"
    ERROR = "error"

class StateMachineCoordinator:
    def __init__(self, agents):
        self.agents = agents
        self.agent_states = {a.agent_id: AgentState.IDLE for a in agents}

    def update_state(self, agent_id: str, new_state: AgentState):
        self.agent_states[agent_id] = new_state
        self._check_transitions()

    def _check_transitions(self):
        # Check if all agents completed
        if all(s == AgentState.COMPLETED for s in self.agent_states.values()):
            self._finalize()

        # Check if any agent errored
        if any(s == AgentState.ERROR for s in self.agent_states.values()):
            self._handle_failure()
```

---

## Communication Patterns

### Event-Based Communication (Recommended)

Agents communicate through events on a shared bus.

```python
from asyncio import Queue
from typing import Callable, Dict, Any

class EventBus:
    def __init__(self):
        self._subscribers: list[Queue] = []

    async def publish(self, event: dict):
        """Publish event to all subscribers."""
        for queue in self._subscribers:
            await queue.put(event)

    def subscribe(self) -> Queue:
        """Create new subscription, returns queue of events."""
        queue = Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: Queue):
        """Remove subscription."""
        self._subscribers.remove(queue)


# Usage in agent
class MyAgent:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def analyze(self, code: str):
        await self.event_bus.publish({
            "event_type": "agent_started",
            "agent_id": self.agent_id,
            "data": {"task": "Analyzing code"}
        })

        # ... do work ...

        await self.event_bus.publish({
            "event_type": "finding_discovered",
            "agent_id": self.agent_id,
            "data": {...}
        })
```

---

### Direct Messaging (Optional Bonus)

Agents can send messages directly to each other.

```python
class DirectMessaging:
    def __init__(self):
        self._mailboxes: Dict[str, Queue] = {}

    def register_agent(self, agent_id: str):
        self._mailboxes[agent_id] = Queue()

    async def send(self, from_agent: str, to_agent: str, message: dict):
        if to_agent in self._mailboxes:
            await self._mailboxes[to_agent].put({
                "from": from_agent,
                "message": message
            })

    async def receive(self, agent_id: str) -> dict:
        return await self._mailboxes[agent_id].get()

    def has_message(self, agent_id: str) -> bool:
        return not self._mailboxes[agent_id].empty()
```

---

## Shared Memory Patterns

### Shared Context Object

All agents read/write to a shared context.

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any
import threading

@dataclass
class SharedContext:
    """Thread-safe shared context for agents."""
    code: str
    metadata: dict = field(default_factory=dict)
    findings: List[dict] = field(default_factory=list)
    agent_results: Dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_finding(self, finding: dict):
        with self._lock:
            self.findings.append(finding)

    def set_agent_result(self, agent_id: str, result: Any):
        with self._lock:
            self.agent_results[agent_id] = result

    def get_findings_by_agent(self, agent_id: str) -> List[dict]:
        with self._lock:
            return [f for f in self.findings if f.get("agent_id") == agent_id]

    def get_all_findings(self) -> List[dict]:
        with self._lock:
            return self.findings.copy()
```

---

### Blackboard Pattern

Central "blackboard" where agents post and read information.

```python
class Blackboard:
    """Shared knowledge base for agents."""

    def __init__(self):
        self._data = {}
        self._lock = asyncio.Lock()
        self._watchers = []

    async def write(self, key: str, value: Any, agent_id: str):
        async with self._lock:
            self._data[key] = {
                "value": value,
                "written_by": agent_id,
                "timestamp": datetime.utcnow()
            }
        # Notify watchers
        for callback in self._watchers:
            await callback(key, value, agent_id)

    async def read(self, key: str) -> Any:
        async with self._lock:
            entry = self._data.get(key)
            return entry["value"] if entry else None

    async def query(self, prefix: str) -> Dict[str, Any]:
        async with self._lock:
            return {
                k: v["value"]
                for k, v in self._data.items()
                if k.startswith(prefix)
            }

    def watch(self, callback):
        self._watchers.append(callback)
```

---

## Error Handling Patterns

### Graceful Degradation

Continue with available results if some agents fail.

```python
class ResilientCoordinator:
    async def execute(self, code: str, event_callback):
        results = []

        for agent in self.agents:
            try:
                result = await asyncio.wait_for(
                    agent.analyze(code, event_callback),
                    timeout=60.0  # 60 second timeout per agent
                )
                results.append(result)
            except asyncio.TimeoutError:
                event_callback(agent_error_event(
                    agent.agent_id,
                    "Timeout after 60 seconds",
                    recoverable=False
                ))
            except Exception as e:
                event_callback(agent_error_event(
                    agent.agent_id,
                    str(e),
                    recoverable=True
                ))

        # Continue with whatever results we have
        if results:
            return self._consolidate(results)
        else:
            raise AllAgentsFailedError("No agents completed successfully")
```

---

### Retry with Backoff

Retry failed agents with exponential backoff.

```python
class RetryingAgent:
    def __init__(self, agent: BaseAgent, max_retries: int = 3):
        self.agent = agent
        self.max_retries = max_retries

    async def analyze(self, code: str, event_callback) -> Any:
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await self.agent.analyze(code, event_callback)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # 1, 2, 4 seconds
                    event_callback(agent_error_event(
                        self.agent.agent_id,
                        f"Attempt {attempt + 1} failed, retrying in {delay}s",
                        recoverable=True,
                        will_retry=True
                    ))
                    await asyncio.sleep(delay)

        raise last_error
```

---

## Event Bus Implementation

### Complete Event Bus with WebSocket Integration

```python
import asyncio
import json
from datetime import datetime
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dataclasses import dataclass, asdict

@dataclass
class AgentEvent:
    event_type: str
    agent_id: str
    timestamp: str
    data: dict

    def to_json(self) -> str:
        return json.dumps(asdict(self))

class EventBus:
    def __init__(self):
        self._websockets: Set[WebSocket] = set()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._history: list[AgentEvent] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._websockets.add(websocket)

        # Optionally send history to new connections
        for event in self._history[-100:]:  # Last 100 events
            await websocket.send_text(event.to_json())

    def disconnect(self, websocket: WebSocket):
        self._websockets.discard(websocket)

    async def publish(self, event_type: str, agent_id: str, data: dict):
        event = AgentEvent(
            event_type=event_type,
            agent_id=agent_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            data=data
        )

        self._history.append(event)

        # Broadcast to all connected clients
        disconnected = set()
        for ws in self._websockets:
            try:
                await ws.send_text(event.to_json())
            except:
                disconnected.add(ws)

        self._websockets -= disconnected

    def create_callback(self, agent_id: str):
        """Create a callback function for an agent to emit events."""
        async def callback(event_type: str, data: dict):
            await self.publish(event_type, agent_id, data)
        return callback


# FastAPI integration
app = FastAPI()
event_bus = EventBus()

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await event_bus.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive_text()
            # Handle client messages (e.g., start review)
    except WebSocketDisconnect:
        event_bus.disconnect(websocket)
```

---

### Agent Base Class with Event Emission

```python
from abc import ABC, abstractmethod
from typing import Callable, Any

class BaseAgent(ABC):
    def __init__(self, agent_id: str, event_callback: Callable):
        self.agent_id = agent_id
        self._emit = event_callback

    async def emit(self, event_type: str, data: dict):
        await self._emit(event_type, data)

    async def emit_thinking(self, chunk: str):
        await self.emit("thinking", {"chunk": chunk})

    async def emit_finding(self, finding: dict):
        await self.emit("finding_discovered", finding)

    async def emit_tool_call(self, tool_name: str, input_data: dict, purpose: str):
        await self.emit("tool_call_start", {
            "tool_call_id": str(uuid.uuid4()),
            "tool_name": tool_name,
            "input": input_data,
            "purpose": purpose
        })

    @abstractmethod
    async def analyze(self, code: str, context: dict) -> dict:
        """Analyze code and return findings."""
        pass
```

---

## Example: Complete Multi-Agent System

Here's how these patterns come together:

```python
# main.py
import asyncio
from fastapi import FastAPI, WebSocket
from agents import SecurityAgent, BugAgent, Coordinator
from event_bus import EventBus

app = FastAPI()
event_bus = EventBus()

# Create agents
security_agent = SecurityAgent("security_agent", event_bus.create_callback("security_agent"))
bug_agent = BugAgent("bug_agent", event_bus.create_callback("bug_agent"))
coordinator = Coordinator(
    [security_agent, bug_agent],
    event_bus.create_callback("coordinator")
)

@app.websocket("/ws/review")
async def review_websocket(websocket: WebSocket):
    await event_bus.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            if message["type"] == "start_review":
                # Run review in background
                asyncio.create_task(
                    coordinator.execute_review(message["code"])
                )
    except:
        event_bus.disconnect(websocket)

@app.post("/api/review")
async def start_review(code: str):
    """Start a code review (for non-WebSocket clients)."""
    task = asyncio.create_task(coordinator.execute_review(code))
    return {"status": "started", "task_id": str(id(task))}
```

---

## Summary

| Pattern | When to Use |
|---------|-------------|
| Coordinator-Worker | Default choice, clear hierarchy |
| Pipeline | When order matters, simpler logic |
| Parallel Fan-Out | When speed matters, independent tasks |
| Event Bus | Always - for observability |
| Shared Context | When agents need to see each other's findings |
| Retry with Backoff | For API calls and unreliable operations |

**Recommended approach for this assessment:**
1. Use Coordinator-Worker pattern
2. Implement parallel execution for specialist agents
3. Use Event Bus for all communication
4. Shared Context for findings and metadata
5. Graceful degradation for error handling
