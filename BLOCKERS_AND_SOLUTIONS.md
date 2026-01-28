# Blockers & Solutions Log

## Instructions

Document challenges encountered during development and how you resolved them. This helps us understand your problem-solving approach and debugging skills.

**When to update this document:**
- When you hit a significant blocker (>30 min stuck)
- After solving a challenging problem
- When you make important architectural decisions

---

## Blocker Log

### Blocker #1 True Parallelism (Not “fake parallelism”)

**Date/Time:** 01/26/26 – 01/28/26 (iterative)

**Category:** [ ] API/SDK [x ] Architecture [ x] Streaming [ ] UI [ ] Testing [ ] Other

**Description:**
_What was the problem? Be specific._


```
Multi-agent execution *looked* parallel at the graph level, but in practice the system behaved sequentially and/or stalled during consolidation. Tool execution and Claude calls were blocking the event loop, and the coordinator fan-out/fan-in flow did not reliably converge.

```

**Impact:**
_What couldn't you do because of this?_

1) Agents appeared to run one after another

2) Consolidation node separated and hard to reason about

3) Inconsistent agent completion / plan-step completion events

4) INVALID_CONCURRENT_GRAPH_UPDATE in LangGraph for concurrent updates


**Investigation Steps:**


1. Instrumented start/end timestamps and emitted `mode_changed`, `tool_call_start`, `agent_completed` events per agent.
2. Verified which operations were blocking the event loop (Claude SDK call + tool execution).
3. Traced LangGraph state updates to identify which keys were being written concurrently.

**Root Cause:**
_What was actually causing the issue?_

- Blocking operations ran on the event loop (sync Claude SDK + tool execution).
- Graph state keys (`*_completed`, plan step keys) were written concurrently without an annotated reducer, triggering invalid concurrent update errors.



**Solution:**
_How did you fix it?_

- Ran blocking Claude calls and tool execution off the event loop using `asyncio.to_thread(...)`.
- Simplified agent return contract to deterministic `{text, tool_uses, stop_reason}` and centralized consolidation in coordinator.
- Adjusted state updates to avoid multiple concurrent writes to the same key; used explicit step IDs list and published step completion per step.


```python
# Offload sync Claude SDK + tool exec to worker threads
response = await asyncio.to_thread(
    self.client.messages.create,
    model=self.config.model,
    max_tokens=4096,
    system=self.system_prompt,
    messages=messages,
    tools=tools,
)

result = await asyncio.to_thread(execute_tool, tu.name, inp)
```

**Time Spent:** 1 - 1.5 hours

**Lessons Learned:**
_What would you do differently next time?_

“Parallel graph” ≠ parallel runtime. You must protect the event loop and state writes.

Make agent outputs deterministic and coordinator-owned for fan-in to reduce race conditions.


---

### Blocker #2 — Event-Driven Execution Plan + Fix Mapping (Plan ticks + “missing fixes”)

**Date/Time:** 01/27/26

**Category:** [ ] API/SDK [x] Architecture [x] Streaming [x] UI [ ] Testing [x] Other

**Description:**
The execution plan rendered in the UI, but step completion ticks (✓) did not reliably update, and some findings stayed in “Waiting for fix…” even though fixes were generated and filtered upstream. Both symptoms pointed to the same underlying issue: **event identity consistency + ordering across the EventBus → frontend renderer**.

**Impact:**
- UI appeared “stuck” and less trustworthy despite backend completing analysis.
- Reduced confidence in orchestration and end-to-end determinism (finding ↔ fix pairing + step progress).

**Investigation Steps:**
1. Logged every event emitted by backend with `plan_id`, `step_id`, `agent_id`, `finding_id` and compared to what UI expects.
2. Verified frontend routing in `handleEvent()` → `updatePlanStep()` and `updateFindingWithFix()`.
3. Checked ID consistency between:
   - plan JSON step IDs vs emitted `plan_step_*` events
   - `finding.finding_id` (DOM anchor) vs fix event `finding_id`
4. Confirmed naming consistency (`security_agent` vs `secure_agent`, etc.) used in events and UI section keys.

**Root Cause:**

A single architectural issue across EventBus/streaming: **inconsistent identifiers + mismatched event payload fields**.
- Backend sometimes emitted hardcoded step IDs (e.g., “step_3”) or step IDs that didn’t match the coordinator-generated plan steps shown in UI.
- Fix events occasionally used a different identifier than the DOM anchor created from findings (`finding_id` mismatch), so the UI couldn’t attach fixes.
- Minor agent_id naming drift caused some events to be routed to the wrong UI bucket.

**Solution:**
Standardized the event contract so the UI could deterministically bind updates:

1) **Plan IDs / Step IDs (single source of truth)**
- Treat the coordinator plan output as canonical.
- Emit `plan_step_started` and `plan_step_completed` using exactly the same `step_id` values the UI rendered from `plan_created`.


```python
# Coordinator: emit events for each planned step using canonical step_id
for step in state["plan"]["steps"]:
    await bus.publish(create_plan_step_started_event(plan_id, step["step_id"], step["agent"]))
    # ... execute step ...
    await bus.publish(create_plan_step_completed_event(plan_id, step["step_id"], step["agent"], True, duration_ms))
```

2) **Finding ↔ Fix mapping (canonical finding_id)**

i) Generate finding_id once and reuse everywhere.

ii) Ensure fix_proposed event always includes finding_id that matches the finding used to create DOM element fix-content-${findingId}.

**Time Spent:** 1.0–1.5 hours

**Lessons Learned:**



---

### Blocker #3

**Date/Time:** _______________

**Category:** [ ] API/SDK [ ] Architecture [ ] Streaming [ ] UI [ ] Testing [ ] Other

**Description:**



**Impact:**



**Investigation Steps:**
1.
2.
3.

**Root Cause:**



**Solution:**



**Time Spent:** ___ hours

**Lessons Learned:**



---

*(Add more blockers as needed)*

---

## Architectural Decisions

Document significant design decisions and the reasoning behind them.

### Decision #1  Coordinator-Owned Orchestration + Deterministic Fan-in

**Topic:** Coordinator-Owned Orchestration + Deterministic Fan-in

**Options Considered:**

| Option                                          | Pros                                            | Cons                                        |
| ----------------------------------------------- | ----------------------------------------------- | ------------------------------------------- |
| Agents directly coordinate each other           | Less coordinator logic                          | Hard to debug, inconsistent state ownership |
| Coordinator owns plan + fan-out/fan-in (chosen) | Deterministic, testable, single source of truth | Requires careful event design               |
| External queue/workers                          | Scales well                                     | Overkill for assessment scope               |


**Decision:**

Coordinator generates plan → dispatches security + bug in parallel → consolidates findings/fixes → emits final report + per-step events.

**Reasoning:**

Simplifies correctness and observability: one orchestration authority, cleaner UI event mapping, and deterministic final output.

---

### Decision #2 Event-Driven Architecture with a Single Canonical EventBus

**Topic:** Consistent real-time streaming (WebSocket/SSE) + deterministic UI updates across multiple agents

**Problem to solve:**  
I needed the UI to reflect *exactly* what happened in the backend—agent status, plan progress (✓ ticks), tool calls, findings, and fixes—without missing updates or showing stale state.

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **A) Single canonical EventBus (chosen)** | One source of truth; simple mental model; consistent IDs; easiest to debug; works for WS + SSE | Requires upfront schema discipline; all emitters must comply |
| B) Separate EventBus per agent + coordinator merges | Isolation by component; easier unit tests | Event ordering issues; schema drift; harder UI correlation; “ghost states” in UI |
| C) Direct UI updates from agents (tight coupling) | Fast to prototype | Breaks separation; brittle; hard to replay/debug; difficult to support SSE + WS cleanly |

**Decision:**  
Use **one canonical EventBus instance** for the entire system. All agents publish events to the same bus. The server layer (WS/SSE) subscribes once and forwards events to the UI.

**Reasoning:**  
A multi-agent system is inherently concurrent; the UI must not depend on implied ordering or ad-hoc state reconstruction. A single bus enforces:
- one event contract,
- consistent identifiers (`plan_id`, `step_id`, `finding_id`, `agent_id`),
- deterministic UI correlation (plan ticks and fix attachment always match).

### Decision #3 True Parallelism (Non-blocking Claude + Tool Execution)

**Topic:** Avoiding “fake parallelism” while running multiple agent analyses concurrently

**Options Considered:**

| Option | Pros | Cons |
|--------|------|------|
| **A) Async orchestration + `asyncio.to_thread()` for sync SDK/tooling (chosen)** | Real concurrency; keeps event loop responsive; works with sync Claude SDK | Need careful return types + serialization |
| B) Sequential agent calls | Simple | Slow; defeats multi-agent value |
| C) Multiprocessing | True parallel CPU | Heavy; shared state + event bus complexity |

**Decision:**  
Run security + bug agents concurrently using async orchestration. Offload blocking Claude SDK calls and tool execution to threads via `asyncio.to_thread()`.

**Reasoning:**  
This kept the UI responsive (events streaming continuously), prevented the event loop from blocking, and achieved actual overlap in agent execution rather than time-sliced sequential calls.

---

## Known Issues / Technical Debt

List any known issues or shortcuts you took due to time constraints.

| Issue                                                        | Severity | Why Not Fixed | Future Fix                                                     |
| ------------------------------------------------------------ | -------- | ------------- | -------------------------------------------------------------- |
| Event schema validation is manual                            | Medium   | Time          | Add pydantic schema + contract tests for events                |
| UI shows only current tool call (not full history)           | Low      | UX preference | Add optional “verbose mode” toggle                             |
| Agent completion/step completion coupling could be tightened | Medium   | Time          | Add a “plan execution state machine” with explicit transitions |

---

## If I Had More Time

What would you improve or add if you had additional time?

### High Priority
1. Add event contract tests: every plan step must start+complete; every fix must map to an existing finding.
2. Add structured logging/tracing (request_id, review_id) across all agents
3. Add replay mode: feed recorded event logs to UI for deterministic demos.

### Medium Priority
1. Add retry/backoff policy at the coordinator level (centralized).
2. Add dedupe heuristics (semantic + line-range overlap) beyond exact ID matching.
3. Add unit tests for _verify_fixes_findings() pipeline.

### Nice to Have
1. Support incremental streaming updates to findings as soon as a step completes.
2. Expand security patterns and add CWE mapping.
3. Add export button (JSON report download).

---

## Resources Used

List helpful resources you found during development.

### Documentation
- Anthropic Messages API (tools + streaming payload formats)
- LangGraph concurrency/state update rules

### Stack Overflow / Forums
- asyncio event loop + to_thread patterns
- FastAPI WebSocket + SSE patterns

### Code Examples / Repos
-

### AI Assistance
- [ ] Used AI assistance (ChatGPT, Claude, Copilot, etc.)
- Describe how:

---

## Summary Statistics
| Metric                         | Value                                                    |
| ------------------------------ | -------------------------------------------------------- |
| Total blockers encountered     | 2                                                        |
| Average resolution time        | ~0.75 hours                                              |
| Most challenging area          | True parallel execution + consistent state/event updates |
| Time spent debugging vs coding | ~35% debugging / 65% coding                              |


