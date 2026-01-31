# Senior AI/ML Engineer Take-Home Assessment

## Multi-Agent Code Review System with Real-Time Observability

Welcome to the DesignForge AI Engineering assessment. This exercise evaluates your ability to design, build, and deploy production-grade multi-agent AI systems.

**Time Estimate:** 15-25 hours (depending on experience)

---

## What You'll Build

A **multi-agent system** that reviews Python code for bugs, security vulnerabilities, and code quality issues - with a **real-time streaming UI** that shows exactly what each agent is doing, thinking, and communicating.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CODE REVIEW AGENT SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Coordinator │───▶│SecurityAgent │    │  BugAgent    │          │
│  │    Agent     │───▶│              │    │              │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 EVENT STREAM (WebSocket/SSE)                 │   │
│  │  plan → thinking → tool_call → finding → fix_proposed → ... │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    STREAMING UI                              │   │
│  │  Real-time visualization of all agent activity               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why This Assignment?

At DesignForge, we build AI systems that generate and debug code for complex engineering domains. This assignment mirrors our production architecture:

- **Multi-agent coordination** for complex tasks
- **Real-time streaming** so users see what's happening
- **Observable AI systems** - not black boxes
- **Autonomous debugging** - agents that fix what they find

---

## Quick Start

### 1. Read Everything First

Before writing any code, read these documents in order:

1. `PROJECT_REQUIREMENTS.md` - Detailed specifications
2. `STREAMING_EVENTS_SPEC.md` - Event schema you must implement
3. `EVALUATION_RUBRIC.md` - How you'll be scored
4. `CLAUDE_SDK_REFERENCE.md` - Claude API patterns
5. `AGENT_PATTERNS_REFERENCE.md` - Multi-agent design guidance
6. `PRESENTATION_OUTLINE.md` - **Final presentation requirements** (includes advanced discussion topics)

### 2. Submit Your Time Estimate

Fill out `TIME_ESTIMATION.md` with your task breakdown and estimates **before coding**.

### 3. Set Up Your Environment

```bash
# Clone your repository
git clone <your-repo-url>
cd ai-engineer-assessment

# Create Python environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r starter_code/requirements.txt

# Set up API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Run the server
python -m starter_code.src.main --server --port 8080

# Open the link in browser
http://0.0.0.0:8080/

```

### 4. Build Incrementally

Recommended order:
1. Basic agent that calls Claude API
2. Event streaming infrastructure
3. Coordinator + one specialist agent
4. Streaming UI (basic)
5. Second specialist agent
6. Autonomous fix proposals
7. Polish and documentation

### 5. Commit Frequently

We review your git history. Commit every 1-2 hours with meaningful messages.

---

## Deliverables

### Required

| Deliverable | Description |
|-------------|-------------|
| **Multi-agent backend** | Coordinator + 2+ specialist agents |
| **Event streaming** | WebSocket/SSE API emitting all agent events |
| **Streaming UI** | Real-time visualization of agent activity |
| **Test harness results** | Run against `test_cases/`, report metrics |
| **Documentation** | README with setup, architecture, decisions |
| **Technical Presentation** | 30-40 min presentation with live demo (see `PRESENTATION_OUTLINE.md`) |

### Templates to Complete

| File | When |
|------|------|
| `TIME_ESTIMATION.md` | Before AND after coding |
| `BLOCKERS_AND_SOLUTIONS.md` | During development |
| `PRESENTATION_OUTLINE.md` | Before submission - **Required for final presentation** |

### Submission

1. Push all code to your GitHub repository
2. Verify it runs from a fresh clone
3. Include clear setup instructions in README
4. Complete all template documents
5. **Prepare your technical presentation (30-40 min) with live demo** - see `PRESENTATION_OUTLINE.md` for required topics including discussion of fine-tuning and Cursor-like experiences

---

## Tech Stack

### Required

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| LLM | Anthropic Claude API |
| Streaming | WebSocket or Server-Sent Events |
| Backend | FastAPI (recommended) or similar |

### Your Choice

| Component | Options |
|-----------|---------|
| UI | Web (React, vanilla JS), Terminal (Rich), or Desktop |
| State management | Your design |
| Agent framework | Build from scratch or use libraries |

---

## Evaluation Summary

| Category | Weight |
|----------|--------|
| Multi-Agent Architecture | 20% |
| Streaming & Events | 20% |
| UI Observability | 15% |
| Code Review Accuracy | 15% |
| Autonomous Debugging | 10% |
| Code Quality | 10% |
| Documentation | 5% |
| Git Practices | 5% |

**Bonus opportunities:** RAG system, MCP server, AWS design, polished UI, high fix rate.

### Technical Presentation (Final Step)

Your submission includes a **30-40 minute technical presentation** that covers:
- Architecture overview and design decisions
- Live demo of your system
- Discussion of **advanced topics** (required):
  - Fine-tuning a code generator for specific syntax
  - **Building a Cursor-like AI coding assistant experience** (must cover)

See `PRESENTATION_OUTLINE.md` for the complete structure and preparation checklist.

See `EVALUATION_RUBRIC.md` for complete scoring details.

---

## What We're Looking For

### Strong Signals

- Clean agent architecture with clear separation of concerns
- Robust event streaming that handles concurrent agents
- UI that makes agent behavior transparent and understandable
- Thoughtful error handling and edge case management
- Clear documentation of design decisions and tradeoffs
- Honest time estimation and blocker documentation
- **Well-prepared presentation** demonstrating system understanding and forward-thinking on AI engineering topics (fine-tuning, Cursor-like experiences)

### Red Flags

- No streaming (polling or batch only)
- Single agent doing everything
- UI that doesn't show real-time updates
- Tool calls hidden from visibility
- API key committed to repository
- Can't run from fresh clone
- Unprepared for presentation or unable to discuss advanced AI engineering topics

---

## Questions?

If you have questions about requirements, reach out to your contact. We're happy to clarify scope but won't provide implementation hints.

Good luck! We're excited to see what you build.

---

**DesignForge AI Engineering Team**
