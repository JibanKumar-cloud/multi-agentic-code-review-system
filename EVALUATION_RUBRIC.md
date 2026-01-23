# Evaluation Rubric

## Scoring Overview

| Category | Weight | Max Points |
|----------|--------|------------|
| Multi-Agent Architecture | 20% | 20 |
| Streaming & Events | 20% | 20 |
| UI Observability | 15% | 15 |
| Code Review Accuracy | 15% | 15 |
| Autonomous Debugging | 10% | 10 |
| Code Quality | 10% | 10 |
| Documentation | 5% | 5 |
| Git Practices | 5% | 5 |
| **Base Total** | **100%** | **100** |
| Bonus Points | - | +30 |
| **Maximum Possible** | - | **130** |

---

## Detailed Scoring

### 1. Multi-Agent Architecture (20 points)

#### Agent Design (8 points)

| Score | Criteria |
|-------|----------|
| 8 | Excellent: Clean separation of concerns, well-defined interfaces, extensible design |
| 6-7 | Good: Clear agent boundaries, reasonable interfaces |
| 4-5 | Adequate: Agents exist but boundaries are blurry |
| 2-3 | Poor: Agents are tightly coupled or poorly defined |
| 0-1 | Missing: Single agent or no clear architecture |

**Evaluator questions:**
- Can I easily add a new specialist agent?
- Are agent responsibilities clear and non-overlapping?
- Is there a clean interface/contract for agents?

#### Coordination Logic (7 points)

| Score | Criteria |
|-------|----------|
| 7 | Excellent: Sophisticated coordination, handles parallel execution, manages dependencies |
| 5-6 | Good: Clear coordination flow, handles basic parallelism |
| 3-4 | Adequate: Sequential coordination works |
| 1-2 | Poor: Coordination is fragile or hardcoded |
| 0 | Missing: No coordinator, agents work in isolation |

**Evaluator questions:**
- Does the coordinator manage agent lifecycle properly?
- Are parallel agents handled correctly?
- How does it handle agent failures?

#### Shared Context / Memory (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Excellent: Agents share context intelligently, context evolves appropriately |
| 3-4 | Good: Shared state exists and is used |
| 1-2 | Adequate: Basic data passing between agents |
| 0 | Missing: No shared context mechanism |

---

### 2. Streaming & Events (20 points)

#### Event Schema Compliance (8 points)

| Score | Criteria |
|-------|----------|
| 8 | All events conform to spec, proper typing, consistent structure |
| 6-7 | Most events conform, minor deviations |
| 4-5 | Core events work, some missing or non-conforming |
| 2-3 | Events exist but don't follow spec |
| 0-1 | No event system or completely non-conforming |

**Evaluator check:**
- Compare emitted events against `STREAMING_EVENTS_SPEC.md`
- Validate required fields present
- Check timestamp format

#### WebSocket/SSE Implementation (7 points)

| Score | Criteria |
|-------|----------|
| 7 | Robust implementation, handles disconnects, efficient |
| 5-6 | Works reliably, basic error handling |
| 3-4 | Functions but fragile |
| 1-2 | Partial implementation, doesn't handle edge cases |
| 0 | No streaming (polling only) |

**Evaluator check:**
- Open multiple connections simultaneously
- Disconnect and reconnect during review
- Check for memory leaks

#### Real-Time Performance (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Events arrive <100ms from occurrence, smooth streaming |
| 3-4 | Minor delays but acceptable |
| 1-2 | Noticeable batching or delays |
| 0 | Not real-time (polling or large batches) |

**Evaluator check:**
- Are `thinking` events truly streaming?
- Do events arrive as they happen?

---

### 3. UI Observability (15 points)

#### Agent Status Display (5 points)

| Score | Criteria |
|-------|----------|
| 5 | All agents visible, states clear, updates instantly |
| 3-4 | Agents shown, states update with minor delay |
| 1-2 | Basic agent list, states not clear |
| 0 | No agent visibility |

#### Tool Call Visibility (5 points)

| Score | Criteria |
|-------|----------|
| 5 | All tool calls shown with inputs, outputs, timing |
| 3-4 | Tool calls visible, some details missing |
| 1-2 | Partial tool visibility |
| 0 | Tool calls hidden from UI |

#### Findings & Thoughts Display (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Thoughts stream smoothly, findings appear instantly with full details |
| 3-4 | Both work, minor issues |
| 1-2 | Basic display, not smooth |
| 0 | Not shown in UI |

---

### 4. Code Review Accuracy (15 points)

#### Precision (5 points)

`Precision = True Positives / (True Positives + False Positives)`

| Score | Precision |
|-------|-----------|
| 5 | ≥ 0.85 |
| 4 | 0.75 - 0.84 |
| 3 | 0.65 - 0.74 |
| 2 | 0.55 - 0.64 |
| 1 | 0.45 - 0.54 |
| 0 | < 0.45 |

#### Recall (5 points)

`Recall = True Positives / (True Positives + False Negatives)`

| Score | Recall |
|-------|--------|
| 5 | ≥ 0.85 |
| 4 | 0.75 - 0.84 |
| 3 | 0.65 - 0.74 |
| 2 | 0.55 - 0.64 |
| 1 | 0.45 - 0.54 |
| 0 | < 0.45 |

#### Finding Quality (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Findings are detailed, actionable, correctly located |
| 3-4 | Findings are useful, minor issues with details |
| 1-2 | Findings are vague or imprecise |
| 0 | Findings are not useful |

---

### 5. Autonomous Debugging (10 points)

#### Fix Proposals (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Fixes proposed for most findings, explanations clear |
| 3-4 | Fixes for some findings, reasonable quality |
| 1-2 | Few fixes, or poor quality |
| 0 | No fix proposals |

#### Fix Verification (5 points)

| Score | Criteria |
|-------|----------|
| 5 | Fixes are tested, >70% verify successfully |
| 3-4 | Some verification, 50-70% success |
| 1-2 | Attempted verification, <50% success |
| 0 | No verification attempted |

---

### 6. Code Quality (10 points)

#### Structure & Organization (4 points)

| Score | Criteria |
|-------|----------|
| 4 | Clean architecture, logical file organization, clear modules |
| 3 | Good structure, minor issues |
| 2 | Acceptable but messy |
| 1 | Poor organization |
| 0 | Chaotic structure |

#### Readability (3 points)

| Score | Criteria |
|-------|----------|
| 3 | Clear naming, appropriate comments, easy to follow |
| 2 | Readable with minor issues |
| 1 | Hard to follow |
| 0 | Unreadable |

#### Best Practices (3 points)

| Score | Criteria |
|-------|----------|
| 3 | Follows Python best practices, proper error handling, type hints |
| 2 | Mostly follows best practices |
| 1 | Some issues |
| 0 | Ignores best practices |

---

### 7. Documentation (5 points)

#### README Quality (2 points)

| Score | Criteria |
|-------|----------|
| 2 | Clear setup instructions, architecture explanation, works from fresh clone |
| 1 | Basic instructions, some gaps |
| 0 | Missing or insufficient |

#### Architecture Documentation (3 points)

| Score | Criteria |
|-------|----------|
| 3 | Clear diagrams, explains decisions, discusses tradeoffs |
| 2 | Good explanation, minor gaps |
| 1 | Basic description |
| 0 | No architecture docs |

---

### 8. Git Practices (5 points)

#### Commit Frequency (2 points)

| Score | Criteria |
|-------|----------|
| 2 | Regular commits (every 1-2 hours), logical progression |
| 1 | Some commits, sparse |
| 0 | Few commits, or single final commit |

#### Commit Message Quality (3 points)

| Score | Criteria |
|-------|----------|
| 3 | Descriptive, follows convention, explains why |
| 2 | Adequate messages |
| 1 | Poor messages ("fix", "update", "wip") |
| 0 | No meaningful messages |

---

## Bonus Points (+30 max)

### Tier 1 Bonuses (+5 points each, max 25)

| Bonus | Points | Criteria |
|-------|--------|----------|
| **RAG System** | +5 | Implements retrieval over Python docs for better analysis |
| **MCP Server** | +5 | Creates custom MCP tool (e.g., code executor) |
| **AWS Design Doc** | +5 | Detailed architecture for Lambda/API Gateway deployment |
| **Polished Web UI** | +5 | Professional, well-designed interface beyond functional |
| **High Fix Rate** | +5 | >70% of proposed fixes verify successfully |

### Tier 2 Bonuses (+3 points each, max 9)

| Bonus | Points | Criteria |
|-------|--------|----------|
| **Additional Agent** | +3 | Style checker, performance analyzer, etc. |
| **Agent-to-Agent Comm** | +3 | Direct messages between specialist agents |
| **Multi-turn Sessions** | +3 | Conversation history and follow-up analysis |

### Tier 3 Bonuses (+2 points each, max 6)

| Bonus | Points | Criteria |
|-------|--------|----------|
| **Cost Optimization** | +2 | Token usage tracking and analysis |
| **Caching** | +2 | Cache repeated analysis patterns |
| **Configuration UI** | +2 | Let users configure agent behavior |

---

## Red Flags (Automatic Deductions)

| Issue | Deduction | Description |
|-------|-----------|-------------|
| **No streaming** | -15 | Polling or batch responses only |
| **Single agent** | -15 | No multi-agent coordination |
| **UI not real-time** | -10 | Events don't stream live |
| **No tool visibility** | -10 | Tool calls hidden from UI |
| **API key in repo** | -10 | Security violation |
| **Doesn't run** | -15 | Can't execute from fresh clone |
| **Plagiarism** | -20 | Copied code without attribution |
| **Lying about time** | -15 | Time estimates clearly fabricated |

---

## Scoring Guide

| Total Score | Assessment | Recommendation |
|-------------|------------|----------------|
| 100+ | Exceptional | Strong hire - demonstrates mastery |
| 85-99 | Excellent | Hire - exceeds expectations |
| 70-84 | Good | Likely hire - meets expectations |
| 55-69 | Adequate | Hire with reservations |
| 40-54 | Below expectations | Probably don't hire |
| <40 | Poor | Don't hire |

---

## Evaluation Checklist

### Before Reviewing

- [ ] Clone candidate's repository
- [ ] Follow README setup instructions exactly
- [ ] Note any setup issues

### Functionality Check

- [ ] System starts without errors
- [ ] Can submit code for review
- [ ] Events stream to UI
- [ ] Multiple agents visible and working
- [ ] Findings appear in real-time
- [ ] Fixes proposed for issues

### Quality Check

- [ ] Run against test_cases/
- [ ] Calculate precision/recall
- [ ] Review code structure
- [ ] Check git history

### Documentation Check

- [ ] TIME_ESTIMATION.md complete
- [ ] BLOCKERS_AND_SOLUTIONS.md filled
- [ ] presentation_outline.md prepared
- [ ] README has architecture section

---

## Evaluator Notes Template

```markdown
# Candidate: [Name]
# Date: [Date]

## Quick Assessment
- [ ] System runs from fresh clone
- [ ] Multi-agent architecture present
- [ ] Events stream in real-time
- [ ] UI shows agent activity

## Scores

| Category | Score | Notes |
|----------|-------|-------|
| Multi-Agent Architecture | /20 | |
| Streaming & Events | /20 | |
| UI Observability | /15 | |
| Code Review Accuracy | /15 | |
| Autonomous Debugging | /10 | |
| Code Quality | /10 | |
| Documentation | /5 | |
| Git Practices | /5 | |
| **Base Total** | /100 | |
| Bonus Points | + | |
| Red Flag Deductions | - | |
| **Final Score** | | |

## Strengths


## Concerns


## Recommendation
[ ] Strong Hire
[ ] Hire
[ ] Hire with Reservations
[ ] Don't Hire

## Notes for Interview

```

---

## Interview Questions (Post-Submission)

After reviewing, prepare questions for the presentation:

### Architecture
1. Walk me through how you designed the agent communication.
2. Why did you choose this coordination pattern?
3. How would you add a fourth agent?

### Technical Depth
4. How do you handle concurrent event emission from multiple agents?
5. What happens if the Security Agent fails mid-review?
6. How would this scale to 1000 concurrent reviews?

### Tradeoffs
7. What tradeoffs did you make for time?
8. If you had another week, what would you improve?
9. What's the most fragile part of your system?

### Production Thinking
10. How would you deploy this to AWS?
11. What monitoring would you add?
12. How would you handle rate limits?
