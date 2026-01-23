# Claude SDK Reference

This document provides code patterns for working with the Anthropic Claude API in the context of this assessment.

---

## Setup

### Installation

```bash
pip install anthropic python-dotenv
```

### Environment

Create `.env` file (add to `.gitignore`):

```
ANTHROPIC_API_KEY=your-api-key-here
```

### Basic Client Setup

```python
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)
```

---

## Basic Message API

### Simple Request

```python
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[
        {"role": "user", "content": "Analyze this Python code for bugs: ..."}
    ]
)

print(message.content[0].text)
```

### With System Prompt

```python
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="You are a senior security engineer reviewing code for vulnerabilities.",
    messages=[
        {"role": "user", "content": "Review this code: ..."}
    ]
)
```

---

## Streaming Responses

### Basic Streaming

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Analyze this code..."}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### Streaming with Event Handling

```python
async def stream_with_events(prompt: str, event_callback):
    """Stream response and emit events for each chunk."""

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        full_response = ""

        for text in stream.text_stream:
            full_response += text

            # Emit thinking event for each chunk
            event_callback({
                "event_type": "thinking",
                "agent_id": "my_agent",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {"chunk": text}
            })

        return full_response
```

---

## Extended Thinking

Claude can show its reasoning process using extended thinking.

### Enable Extended Thinking

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # Max tokens for thinking
    },
    messages=[{"role": "user", "content": "Analyze this code for security issues..."}]
)

# Access thinking and response separately
for block in response.content:
    if block.type == "thinking":
        print("THINKING:", block.thinking)
    elif block.type == "text":
        print("RESPONSE:", block.text)
```

### Streaming Extended Thinking

```python
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000
    },
    messages=[{"role": "user", "content": "..."}]
) as stream:
    current_block_type = None

    for event in stream:
        if hasattr(event, 'type'):
            if event.type == 'content_block_start':
                current_block_type = event.content_block.type
                if current_block_type == 'thinking':
                    print("\n--- THINKING ---")
                elif current_block_type == 'text':
                    print("\n--- RESPONSE ---")

            elif event.type == 'content_block_delta':
                if hasattr(event.delta, 'thinking'):
                    print(event.delta.thinking, end="", flush=True)
                elif hasattr(event.delta, 'text'):
                    print(event.delta.text, end="", flush=True)
```

---

## Tool Use (Function Calling)

### Defining Tools

```python
tools = [
    {
        "name": "execute_code",
        "description": "Execute Python code in a sandboxed environment and return the output",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "read_file",
        "description": "Read contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                }
            },
            "required": ["path"]
        }
    }
]
```

### Making Tool-Enabled Request

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=tools,
    messages=[
        {"role": "user", "content": "Test if this code has a SQL injection vulnerability..."}
    ]
)

# Check if Claude wants to use a tool
for block in response.content:
    if block.type == "tool_use":
        tool_name = block.name
        tool_input = block.input
        tool_use_id = block.id

        print(f"Claude wants to use tool: {tool_name}")
        print(f"With input: {tool_input}")
```

### Complete Tool Use Loop

```python
def run_agent_with_tools(initial_prompt: str, tools: list, tool_handlers: dict):
    """Run an agent that can use tools until it's done."""

    messages = [{"role": "user", "content": initial_prompt}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        # Check if we're done (no tool use)
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            # Extract final text response
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else ""

        # Process tool calls
        tool_results = []
        for tool_use in tool_uses:
            handler = tool_handlers.get(tool_use.name)
            if handler:
                result = handler(tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(result)
                })

        # Add assistant response and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
```

### Tool Use with Events

```python
async def run_agent_with_events(prompt: str, tools: list, handlers: dict, event_callback):
    """Run agent with tools, emitting events for visibility."""

    messages = [{"role": "user", "content": prompt}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else ""

        tool_results = []
        for tool_use in tool_uses:
            # Emit tool_call_start event
            event_callback({
                "event_type": "tool_call_start",
                "agent_id": "my_agent",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {
                    "tool_call_id": tool_use.id,
                    "tool_name": tool_use.name,
                    "input": tool_use.input,
                    "purpose": "Analyzing code"
                }
            })

            start_time = time.time()
            handler = handlers.get(tool_use.name)
            result = handler(tool_use.input) if handler else "Tool not found"
            duration_ms = int((time.time() - start_time) * 1000)

            # Emit tool_call_result event
            event_callback({
                "event_type": "tool_call_result",
                "agent_id": "my_agent",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {
                    "tool_call_id": tool_use.id,
                    "tool_name": tool_use.name,
                    "success": True,
                    "output": result,
                    "duration_ms": duration_ms
                }
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": str(result)
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
```

---

## Structured Output

### Using JSON Mode

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[
        {
            "role": "user",
            "content": """Analyze this code and return findings as JSON:

```python
user_id = request.args.get('id')
query = f"SELECT * FROM users WHERE id = {user_id}"
```

Return format:
{
    "findings": [
        {
            "type": "security|bug|style",
            "severity": "critical|high|medium|low",
            "title": "string",
            "description": "string",
            "line": number,
            "fix": "string"
        }
    ]
}"""
        }
    ]
)

import json
findings = json.loads(response.content[0].text)
```

### Prompting for Structured Output

```python
ANALYSIS_PROMPT = """You are a code security analyzer. Analyze the provided code and return your findings in the following JSON format:

{
    "findings": [
        {
            "finding_id": "unique_id",
            "category": "security" | "bug" | "style",
            "severity": "critical" | "high" | "medium" | "low" | "info",
            "type": "specific_issue_type",
            "title": "Short title",
            "description": "Detailed description",
            "location": {
                "line_start": number,
                "line_end": number,
                "code_snippet": "the problematic code"
            },
            "fix": {
                "proposed_code": "the fixed code",
                "explanation": "why this fixes the issue"
            },
            "confidence": 0.0 to 1.0
        }
    ],
    "summary": "Overall assessment"
}

IMPORTANT: Return ONLY valid JSON, no other text.

Code to analyze:
```python
{code}
```"""
```

---

## Multi-Turn Conversations

### Maintaining Context

```python
class AgentConversation:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.messages = []

    def send(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.system_prompt,
            messages=self.messages
        )

        assistant_message = response.content[0].text
        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message
```

### Agent Communication Pattern

```python
class CodeReviewAgent:
    def __init__(self, agent_id: str, specialty: str):
        self.agent_id = agent_id
        self.system_prompt = f"""You are a {specialty} specialist reviewing code.
Your job is to find {specialty}-related issues and propose fixes.
Be thorough but avoid false positives."""
        self.conversation = AgentConversation(self.system_prompt)

    def analyze(self, code: str, context: dict = None) -> dict:
        prompt = f"Analyze this code for {self.agent_id} issues:\n\n```python\n{code}\n```"

        if context:
            prompt += f"\n\nContext from other agents: {json.dumps(context)}"

        response = self.conversation.send(prompt)
        return self._parse_response(response)
```

---

## Error Handling

### API Errors

```python
import anthropic

try:
    response = client.messages.create(...)
except anthropic.APIConnectionError:
    # Network issue
    print("Failed to connect to API")
except anthropic.RateLimitError:
    # Rate limited - implement backoff
    print("Rate limited, waiting...")
    time.sleep(60)
except anthropic.APIStatusError as e:
    # API returned an error status
    print(f"API error: {e.status_code} - {e.message}")
```

### Retry with Backoff

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except anthropic.RateLimitError:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def call_claude(messages):
    return client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=messages
    )
```

---

## Best Practices

### Token Management

```python
# Check token usage
response = client.messages.create(...)
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")

# Estimate tokens before sending (rough)
def estimate_tokens(text: str) -> int:
    # Rough estimate: ~4 characters per token
    return len(text) // 4
```

### Prompt Engineering for Code Analysis

```python
# Be specific about what you want
SECURITY_PROMPT = """Analyze this Python code for security vulnerabilities.

Focus on:
1. SQL injection
2. Command injection
3. XSS vulnerabilities
4. Hardcoded secrets
5. Insecure deserialization
6. Path traversal

For each finding, provide:
- Exact line number
- Severity (critical/high/medium/low)
- Clear explanation
- Concrete fix

Code:
```python
{code}
```"""

# Provide examples for better output
FEW_SHOT_PROMPT = """Analyze code for bugs. Here's an example:

Input:
```python
def get_user(users, id):
    return users[id]
```

Output:
{
    "findings": [{
        "type": "bug",
        "severity": "medium",
        "title": "Missing key check",
        "line": 2,
        "description": "Accessing dict without checking if key exists",
        "fix": "return users.get(id)"
    }]
}

Now analyze:
```python
{code}
```"""
```

---

## Testing Your Integration

### Simple Test Script

```python
#!/usr/bin/env python3
"""Test script to verify Claude API integration."""

import os
from dotenv import load_dotenv
import anthropic

def test_basic_api():
    """Test basic API connectivity."""
    load_dotenv()

    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": "Say 'API working!' and nothing else."}]
    )

    result = response.content[0].text
    assert "API working" in result, f"Unexpected response: {result}"
    print("✓ Basic API test passed")

def test_streaming():
    """Test streaming responses."""
    load_dotenv()
    client = anthropic.Anthropic()

    chunks = []
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{"role": "user", "content": "Count from 1 to 5."}]
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)

    assert len(chunks) > 1, "Streaming should produce multiple chunks"
    print(f"✓ Streaming test passed ({len(chunks)} chunks)")

def test_tool_use():
    """Test tool calling."""
    load_dotenv()
    client = anthropic.Anthropic()

    tools = [{
        "name": "calculator",
        "description": "Perform arithmetic",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        }
    }]

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        tools=tools,
        messages=[{"role": "user", "content": "What is 2 + 2? Use the calculator."}]
    )

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    assert len(tool_uses) > 0, "Should have tool use"
    print("✓ Tool use test passed")

if __name__ == "__main__":
    test_basic_api()
    test_streaming()
    test_tool_use()
    print("\nAll tests passed!")
```

---

## Resources

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Python SDK Reference](https://github.com/anthropics/anthropic-sdk-python)
- [Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [Tool Use Documentation](https://docs.anthropic.com/claude/docs/tool-use)
