"""
Base agent class that all specialized agents inherit from.
Provides Claude API integration with streaming and tool use.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import json
import uuid
import logging
import time

import anthropic
from ..config import AgentConfig, config
from .state import ReviewState

from ..events import (
    Event, EventBus,
    create_agent_error_event,
    create_mode_changed_event,
    create_tool_call_start_event,
    create_tool_call_result_event
)
from ..tools import execute_tool, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    
    Provides:
    - Claude API client initialization
    - Event publishing helpers
    - Tool execution framework
    - Streaming support
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        agent_config: AgentConfig,
        event_bus: EventBus,
    ):
        """
        Initialize the base agent.
        
        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (coordinator, security, bug)
            agent_config: Configuration for this agent
            event_bus: Event bus for publishing events
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = agent_config
        self.event_bus = event_bus

        
        # Initialize Claude client
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        
        # Conversation history for multi-turn
        self.messages: List[Dict[str, Any]] = []
        
        # Track state
        self._start_time: Optional[float] = None
        self._findings: List[Dict[str, Any]] = []
        self._fixes: List[Dict[str, Any]] = []
        
        # Token/Cost tracking
        self._token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "api_calls": 0,
            "estimated_cost_usd": 0.0
        }
    
    # Token pricing (Claude 3.5 Sonnet)
    TOKEN_PRICING = {
        "input": 3.00 / 1_000_000,   # $3 per 1M input tokens
        "output": 15.00 / 1_000_000  # $15 per 1M output tokens
    }
    
    def track_tokens(self, input_tokens: int, output_tokens: int):
        """Track token usage and calculate costs."""
        self._token_usage["input_tokens"] += input_tokens
        self._token_usage["output_tokens"] += output_tokens
        self._token_usage["total_tokens"] += (input_tokens + output_tokens)
        self._token_usage["api_calls"] += 1
        
        # Calculate cost
        input_cost = input_tokens * self.TOKEN_PRICING["input"]
        output_cost = output_tokens * self.TOKEN_PRICING["output"]
        self._token_usage["estimated_cost_usd"] += (input_cost + output_cost)
    
    def get_token_usage(self) -> Dict[str, Any]:
        """Get current token usage statistics."""
        return {
            **self._token_usage,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type
        }
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the tools available to this agent."""
        pass
    
    @abstractmethod
    async def analyze(
        self,
        state: ReviewState,
    ) -> Dict[str, Any]:
        """
        Analyze code and return findings.
        
        Args:
            code: The code to analyze
            context: Optional context from other agents
            
        Returns:
            Dictionary containing analysis results
        """
        pass
    
    def _publish_event(self, event: Event) -> None:
        """Helper to publish events synchronously."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.event_bus.publish(event))
        except RuntimeError:
            self.event_bus.publish_sync(event)
    
    async def _publish_event_async(self, event: Event) -> None:
        """Helper to publish events asynchronously."""
        await self.event_bus.publish(event)

    
    async def _call_claude(
        self,
        messages: List[Dict[str, Any]],
        agent_id: int,
        code:str,
        tools: Optional[List[Dict[str, Any]]],
        agent_run_mode: str = "parallel",
        max_iteration: int = 10
  
    ) -> Dict[str, Any]:
        """
        Make a call to Claude API with streaming, tool use, parallel multi-agentic and extended thinking support.
        
        Args:
            messages: Conversation messages
            tools: Optional tools to enable
            use_streaming: Whether to stream the response
            use_thinking: Whether to enable extended thinking (for complex analysis)
            
        Returns:
            Dictionary with response content, any tool uses, and thinking content
        """
        if agent_run_mode == "parallel":
            # Helps multiple agents run asynchronously
            return await self._call_claude_with_parallel(messages, code, agent_id, tools, max_iteration)   
        else:
             return await self._call_claude_streaming(messages, tools)


  

    async def _call_claude_streaming(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call Claude API with streaming and extended thinking support.
        
        Extended thinking allows Claude to reason through complex problems
        before providing a response, improving quality for code analysis.
        """
        from ..events import create_thinking_event
        import asyncio

        full_text = ""
        thinking_text = ""
        tool_uses = []
        current_tool_use = None
        current_tool_input = ""
        current_block_type = None

        if callable(tools):
            tools = tools()
        if tools is not None and not isinstance(tools, list):
            raise TypeError(f"tools must be a list or None, got {type(tools)}")

        kwargs = {
            "model": self.config.model,
            "max_tokens": 9000, # it can be configured 
            "system": [{"type": "text", "text": "You are a code Reviewer Expert agent."}],
            "messages": messages,
            # Enable extended thinking for deeper analysis
            "thinking": {
                "type": "enabled",
                "budget_tokens": 7000  # Allow up to 10K tokens for reasoning
            }
        }
        if tools:
            kwargs["tools"] = tools

        # Get event loop for async publishing
        loop = asyncio.get_event_loop()

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    # Handle content block start
                    if event.type == 'content_block_start':
                        current_block_type = event.content_block.type
                        
                        if current_block_type == 'thinking':
                            # Starting extended thinking block
                            pass
                        elif current_block_type == 'text':
                            # Starting response text block  
                            pass
                        elif current_block_type == 'tool_use':
                            # Starting tool use block
                            current_tool_use = {
                                "id": event.content_block.id, 
                                "name": event.content_block.name, 
                                "input": {}
                            }
                            current_tool_input = ""
                    
                    # Handle content block delta (streaming chunks)
                    elif event.type == 'content_block_delta':
                        # Extended thinking chunks
                        if hasattr(event.delta, 'thinking'):
                            chunk = event.delta.thinking
                            thinking_text += chunk
                            # Stream thinking to UI
                            if chunk:
                                loop.call_soon(
                                    lambda c=chunk: asyncio.ensure_future(
                                        self.event_bus.publish(create_thinking_event(self.agent_id, c))
                                    )
                                )
                        
                        # Response text chunks
                        elif hasattr(event.delta, 'text'):
                            chunk = event.delta.text
                            full_text += chunk
                            # Stream response to UI
                            if chunk:
                                loop.call_soon(
                                    lambda c=chunk: asyncio.ensure_future(
                                        self.event_bus.publish(create_thinking_event(self.agent_id, c))
                                    )
                                )
                        
                        # Tool input JSON chunks
                        elif hasattr(event.delta, 'partial_json'):
                            current_tool_input += event.delta.partial_json
                    
                    # Handle content block stop
                    elif event.type == 'content_block_stop':
                        if current_tool_use is not None:
                            try:
                                current_tool_use["input"] = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            tool_uses.append(current_tool_use)
                            current_tool_use = None
                            current_tool_input = ""
                        current_block_type = None

        stop_reason = None
        try:
            if hasattr(stream, "response") and stream.response:
                stop_reason = getattr(stream.response, "stop_reason", None)
        except Exception:
            pass

        # Track token usage including thinking tokens
        try:
            if hasattr(stream, "response") and stream.response:
                usage = getattr(stream.response, "usage", None)
                if usage:
                    input_tokens = getattr(usage, "input_tokens", 0)
                    output_tokens = getattr(usage, "output_tokens", 0)
                    self.track_tokens(input_tokens, output_tokens)
        except Exception:
            pass

        return {
            "text": full_text, 
            "thinking": thinking_text,
            "tool_uses": tool_uses, 
            "stop_reason": stop_reason
        }

    
    async def _call_claude_with_parallel(self, 
                                         messages: List[Dict[str, Any]], 
                                         code: str, 
                                         agent_id: str, 
                                         tools: List[Dict[str, Any]],
                                         max_iteration: int=10) -> str:
        
        """Single Claude call with tools (NON-BLOCKING)."""

        first_tool = True
        count = 0
   
        for _ in range(max_iteration):
            response = None

            # Forced the agen to return response without tool on too many tool calls
            if count >= max_iteration:
                tools = None

            # ---- Claude call MUST be off the event loop (sync SDK) ----

            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.config.model,
                max_tokens=4096,
                messages=messages,
                tools=tools,
            )

            if not response:
                return ""

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            # If no tool calls, return final text
            if not tool_uses:
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return ""

            if first_tool:
                await self.event_bus.publish(create_mode_changed_event(agent_id, "streaming"))
                first_tool = False

            tool_results = []
            for tu in tool_uses:
                tid = str(uuid.uuid4())
                await self.event_bus.publish(
                    create_tool_call_start_event(agent_id, tid, tu.name, tu.input, f"Executing {tu.name}")
                )

                start = time.time()
                inp = dict(tu.input)
                if "code" not in inp:
                    inp["code"] = code

                # ---- Tool execution MUST be off the event loop too ----
                result = await asyncio.to_thread(execute_tool, tu.name, inp)

                dur = int((time.time() - start) * 1000)
                await self.event_bus.publish(
                    create_tool_call_result_event(agent_id, tid, tu.name, result.success, result.output, dur)
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result.output) if result.success else result.error,
                    }
                )

            # Build assistant content (preserve tool_use blocks)
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append(
                        {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                    )

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            count += 1
        
        return ""

    def reset(self) -> None:
        """Reset the agent's state."""
        self.messages = []
        self._findings = []
        self._fixes = []
        self._start_time = None