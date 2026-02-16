# Multi-Agent Code Review System

A sophisticated AI-powered code review system that uses multiple specialized Claude agents working in parallel to detect security vulnerabilities, bugs, and code quality issues with real-time streaming feedback.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Claude](https://img.shields.io/badge/Claude-3.5%20Sonnet-purple.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket-teal.svg)

---

## 🎯 Project Overview

This system implements a multi-agent architecture where specialized AI agents collaborate to perform comprehensive code reviews:

- **Coordinator Agent**: Creates execution plans, orchestrates other agents, merges and deduplicates findings
- **Security Agent**: Detects SQL injection, XSS, command injection, insecure deserialization, hardcoded secrets
- **Bug Agent**: Identifies null reference errors, race conditions, type errors, logic bugs

### Key Features

| Feature | Description |
|---------|-------------|
| **Parallel Execution** | Security and Bug agents run simultaneously via LangGraph |
| **Extended Thinking** | Claude reasons deeply before responding (10K token budget) |
| **Real-time Streaming** | WebSocket streams agent thoughts, tool calls, and findings live |
| **RAG Integration** | Retrieves from Python docs and security knowledge base |
| **Retry with Backoff** | Exponential backoff on API errors with UI status display |
| **Actionable Fixes** | Every finding includes a suggested code fix |

---

DEMO:

![alt text](<Screenshot 2026-01-30 at 3.38.45 PM.png>)

## 📊 Evaluation Results

```
╔══════════════════════════════════════════════════════════════════╗
║                     EVALUATION METRICS                           ║
╠══════════════════════════════════════════════════════════════════╣
║   Precision:       96.3%  ✅ (target: >85%)                      ║
║   Recall:          82.5%  ✅ (target: >75%)                      ║
║   F1 Score:        88.9%  ✅                                     ║
║   Fix Success:     88.2%  ✅ (target: >70%)                      ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Browser)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │   [Code Input] [Execution Plan] [Agent Status] [Metrics]            │   │
│  │   [Coordinator] [Bug Agent] [Security Agent] - Real-time Thinking   │   │
│  │   [Findings with Severity Badges and Suggested Fixes]               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              WebSocket ↕                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                              BACKEND                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI + WebSocket Server                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          EVENT BUS                                   │   │
│  │              (Pub/Sub for all agent communication)                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│              ┌─────────────────────┼─────────────────────┐                 │
│              ▼                     ▼                     ▼                 │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐        │
│  │    COORDINATOR    │ │   SECURITY AGENT  │ │     BUG AGENT     │        │
│  │  • Creates plan   │ │  • SQL Injection  │ │  • Null refs      │        │
│  │  • Orchestrates   │ │  • XSS, CMDi      │ │  • Race conditions│        │
│  │  • Merges results │ │  • Deserialization│ │  • Type errors    │        │
│  └───────────────────┘ └───────────────────┘ └───────────────────┘        │
│              │                     │                     │                 │
│              └─────────────────────┼─────────────────────┘                 │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TOOL LAYER + RAG                                  │   │
│  │   search_pattern | parse_ast | verify_fix | search_security_docs    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                          Claude 3.5 Sonnet API                              │
│                      (Extended Thinking Enabled)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Anthropic API Key

### Installation

```bash
# 1. Clone and navigate to project
cd ai-engineer-assessment-jiban-fixed

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
cd starter_code
pip install -r requirements.txt

# 4. Set up environment variables
cp ../.env.example ../.env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Configuration

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
MODEL_NAME=claude-sonnet-4-20250514
MAX_TOKENS=16000
```

### Running the Application

```bash
# Start the server
cd starter_code
python -m src.main

# Or directly with uvicorn
uvicorn src.ui.streaming_server:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to: **http://localhost:8000**

---

## 📁 Project Structure

```
ai-engineer-assessment-jiban-fixed/
├── starter_code/
│   ├── src/
│   │   ├── agents/                    # Multi-agent system
│   │   │   ├── base_agent.py          # Base class with Claude API + Extended Thinking
│   │   │   ├── coordinator.py         # Orchestration agent
│   │   │   ├── security_agent.py      # Security vulnerability detection
│   │   │   ├── bug_agent.py           # Bug and error detection
│   │   │   ├── code_review_workflow.py # LangGraph workflow
│   │   │   └── state.py               # Shared ReviewState
│   │   │
│   │   ├── events/                    # Event-driven architecture
│   │   │   ├── event_bus.py           # Pub/Sub event bus
│   │   │   └── event_types.py         # 13 event types + factories
│   │   │
│   │   ├── tools/                     # Agent tools
│   │   │   └── code_tools.py          # search_pattern, parse_ast, verify_fix, etc.
│   │   │
│   │   ├── knowledge_base/            # RAG system
│   │   │   ├── rag_engine.py          # ChromaDB + keyword search
│   │   │   └── docs/
│   │   │       ├── python/            # Python stdlib security docs
│   │   │       ├── owasp/             # OWASP Top 10
│   │   │       └── cwe/               # CWE vulnerability database
│   │   │
│   │   ├── ui/                        # Web interface
│   │   │   └── streaming_server.py    # FastAPI + WebSocket + embedded HTML
│   │   │
│   │   ├── utility/                   # Helpers
│   │   │   ├── retry_utils.py         # Exponential backoff retry
│   │   │   └── retry_errors.py        # Retryable error definitions
│   │   │
│   │   ├── config.py                  # Configuration management
│   │   └── main.py                    # Application entry point
│   │
│   ├── tests/
│   │   ├── test_events.py             # Event system tests
│   │   └── test_harness.py            # Evaluation harness
│   │
│   └── requirements.txt
│
├── test_cases/
│   ├── buggy_samples/                 # 7 test files with known vulnerabilities
│   │   ├── sql_injection.py
│   │   ├── command_injection.py
│   │   ├── xss_vulnerability.py
│   │   ├── insecure_deserialization.py
│   │   ├── hardcoded_secrets.py
│   │   ├── null_reference.py
│   │   └── race_condition.py
│   └── expected_findings.json         # Ground truth for evaluation
│
├── evaluate.py                        # Evaluation script
├── run_evaluation_demo.py             # Demo runner with mock data
├── metrics.json                       # Latest evaluation results
│
├── AWS_ARCHITECTURE.md                # Production deployment design
├── PRESENTATION_GUIDE.md              # Comprehensive presentation notes
└── README.md                          # This file
```

---

## 🔧 Key Components

### 1. Extended Thinking (Claude API)

```python
# base_agent.py - _call_claude_streaming()
kwargs = {
    "model": self.config.model,
    "max_tokens": 16000,
    "thinking": {
        "type": "enabled",
        "budget_tokens": 10000  # Deep reasoning before response
    },
    "messages": messages,
}

with self.client.messages.stream(**kwargs) as stream:
    for event in stream:
        if event.type == 'content_block_delta':
            if hasattr(event.delta, 'thinking'):
                # Stream thinking to UI
                await self.event_bus.publish(create_thinking_event(...))
            elif hasattr(event.delta, 'text'):
                # Stream response to UI
                await self.event_bus.publish(create_thinking_event(...))
```

### 2. Parallel Agent Execution (LangGraph)

```python
# code_review_workflow.py
def build_workflow():
    workflow = StateGraph(ReviewState)
    
    workflow.add_node("coordinator_plan", coordinator.create_plan)
    workflow.add_node("security_agent", security_agent.analyze)
    workflow.add_node("bug_agent", bug_agent.analyze)
    workflow.add_node("coordinator_merge", coordinator.merge_results)
    
    # Parallel execution
    workflow.add_edge("coordinator_plan", "security_agent")
    workflow.add_edge("coordinator_plan", "bug_agent")
    
    # Both complete before merge
    workflow.add_edge("security_agent", "coordinator_merge")
    workflow.add_edge("bug_agent", "coordinator_merge")
    
    return workflow.compile()
```

### 3. Event Streaming (WebSocket)

13 Event Types:
- `review_started`, `review_completed`
- `agent_started`, `agent_completed`, `agent_error`
- `plan_created`, `plan_step_started`, `plan_step_completed`
- `tool_call_start`, `tool_call_result`
- `thinking`
- `finding_discovered`, `fix_proposed`

```python
# Events emitted in real-time
await event_bus.publish(create_finding_event(
    agent_id="security_agent",
    finding_id="sec_001",
    severity="critical",
    category="sql_injection",
    title="SQL Injection in authenticate()",
    description="User input concatenated into query",
    location={"line": 42},
    code_snippet="query = f\"SELECT * FROM users WHERE id = {user_id}\""
))
```

### 4. Retry with Exponential Backoff

```python
# retry_utils.py
for attempt in range(1, policy.max_attempts + 1):
    try:
        return await func()
    except RateLimitError as e:
        if attempt == policy.max_attempts:
            raise
        
        delay = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
        
        # Emit retry event to UI
        await event_bus.publish(create_agent_error_event(
            agent_id=agent_id,
            error=str(e),
            will_retry=True,
            attempt=attempt,
            max_attempts=policy.max_attempts
        ))
        
        await asyncio.sleep(delay)
```

UI displays:
- **"Retrying..."** with badge showing "Retry 1/3"
- **"Incomplete"** when max retries exceeded

### 5. RAG Knowledge Base

```python
# Search security documentation
from src.knowledge_base.rag_engine import search_security_docs

results = search_security_docs(
    query="SQL injection python f-string",
    category="python"  # owasp, cwe, python, fixes
)

# Returns relevant docs like:
# - sqlite3_module.md: Parameterized query examples
# - cwe_89_sql_injection.md: CWE-89 details
# - a03_injection.md: OWASP A03 Injection
```

---

## 🧪 Running Tests

```bash
cd starter_code

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_events.py -v
pytest tests/test_harness.py -v

# Run evaluation
cd ..
python evaluate.py
```

---

## 📈 Evaluation

Run the full evaluation against test cases:

```bash
python evaluate.py
```

This will:
1. Analyze all 7 buggy sample files
2. Compare findings against ground truth
3. Calculate precision, recall, F1 score
4. Verify fix success rate
5. Output detailed metrics

### Expected Output:

```
============================================================
                    EVALUATION RESULTS                      
============================================================
Files analyzed:    7
Expected findings: 63
Found findings:    54
True positives:    52

Precision: 96.3%
Recall:    82.5%
F1 Score:  88.9%

Fix Success Rate: 88.2%
============================================================
```

---

## 🖥️ Web UI Features

### Layout

| Section | Description |
|---------|-------------|
| **Code Input** | Paste code to analyze, click "Analyze Code" |
| **Execution Plan** | Shows coordinator's analysis steps |
| **Agent Status** | Real-time status (Running/Retrying/Completed/Incomplete) |
| **Metrics** | Total findings, severity breakdown, fix count |
| **Agent Activity** | 3 columns showing each agent's tool calls and thinking |
| **Findings** | Dynamic list with severity badges, code snippets, and fixes |

### Status Indicators

| Status | Appearance | Meaning |
|--------|------------|---------|
| 🔵 Running | Blue badge | Agent is working |
| 🟠 Retrying | Orange pulse | API error, retrying (shows attempt count) |
| 🟢 Completed | Green badge | Agent finished successfully |
| 🔴 Incomplete | Red badge | Failed after max retries |

---

## 🔐 Security Vulnerabilities Detected

| Category | Examples |
|----------|----------|
| **SQL Injection** | f-strings in queries, string concatenation |
| **Command Injection** | `os.system()`, `subprocess.run(shell=True)` |
| **XSS** | Unescaped user input in HTML |
| **Insecure Deserialization** | `pickle.load()`, `yaml.load()` |
| **Hardcoded Secrets** | API keys, passwords in code |
| **Null Reference** | Accessing `.attribute` on potentially None |
| **Race Conditions** | TOCTOU, unsynchronized shared state |

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `search_pattern` | Regex search in code |
| `analyze_imports` | Extract and analyze imports |
| `parse_ast` | Parse code into AST |
| `execute_code` | Syntax check execution |
| `verify_fix` | Validate proposed fixes |
| `search_security_docs` | RAG search for security info |

---

## 📚 Documentation Files

| File | Description |
|------|-------------|
| `AWS_ARCHITECTURE.md` | Production deployment with ECS, Lambda, etc. |
| `PRESENTATION_GUIDE.md` | 40-minute presentation with talking points |
| `STREAMING_EVENTS_SPEC.md` | Complete event schema documentation |
| `EVALUATION_RUBRIC.md` | Scoring criteria and bonus points |
| `AGENT_PATTERNS_REFERENCE.md` | Multi-agent design patterns |
| `CLAUDE_SDK_REFERENCE.md` | Anthropic SDK usage guide |

---

## 🚢 Production Deployment

See `AWS_ARCHITECTURE.md` for complete production architecture including:

- **ECS Fargate** for containerized agents
- **API Gateway + Lambda** for serverless API
- **ElastiCache Redis** for distributed event bus
- **SQS** for job queuing
- **CloudWatch** for monitoring
- **Auto-scaling** based on queue depth

---

## 🔮 Future Improvements

### Short-term
- Multi-file analysis (cross-file dependencies)
- Result caching for repeated patterns
- "Apply Fix" button in UI
- Severity filtering in findings

### Medium-term
- GitHub PR integration (post findings as comments)
- Custom rules engine (project-specific patterns)
- Historical trend tracking
- Team dashboard

### Long-term
- Fine-tuned model on false positives/negatives
- User feedback loop for continuous improvement
- Confidence scores on findings

---

## 📝 License

MIT License - See LICENSE file for details.

---

## 🙏 Acknowledgments

- **Anthropic** - Claude API and Extended Thinking
- **LangGraph** - Multi-agent orchestration
- **FastAPI** - High-performance web framework

---

## 📧 Contact

For questions or issues, please open a GitHub issue or contact the maintainer.

---

**Built with ❤️ using Claude 3.5 Sonnet**

