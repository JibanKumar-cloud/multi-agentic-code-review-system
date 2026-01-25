"""
Base agent class that all specialized agents inherit from.
Provides Claude API integration with streaming and tool use.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import asyncio
import json
import uuid
import logging
import time

import anthropic

from ..config import AgentConfig, config
from ..events import (
    Event, EventBus, EventType,
    create_agent_started_event,
    create_agent_completed_event,
    create_agent_error_event,
    create_thinking_event,
    create_thinking_complete_event,
    create_mode_changed_event,
    create_tool_call_start_event,
    create_tool_call_result_event,
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
        event_bus: EventBus
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
        code: str,
        context: Optional[Dict[str, Any]] = None
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
        tools: Optional[List[Dict[str, Any]]] = None,
        use_streaming: bool = True,
        use_thinking: bool = False
    ) -> Dict[str, Any]:
        """
        Make a call to Claude API with streaming, tool use, and extended thinking support.
        
        Args:
            messages: Conversation messages
            tools: Optional tools to enable
            use_streaming: Whether to stream the response
            use_thinking: Whether to enable extended thinking (for complex analysis)
            
        Returns:
            Dictionary with response content, any tool uses, and thinking content
        """
        try:
            if use_thinking:
                return await self._call_claude_with_thinking(messages, tools)
            elif use_streaming:
                return await self._call_claude_streaming(messages, tools)
            else:
                return await self._call_claude_sync(messages, tools)
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            await self._publish_event_async(create_agent_error_event(
                self.agent_id,
                "api_error",
                str(e),
                recoverable=True,
                will_retry=False
            ))
            raise
    
    async def _call_claude_with_thinking(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Call Claude with extended thinking enabled for complex reasoning tasks.
        
        Extended thinking allows Claude to reason through complex problems step-by-step
        before providing a final answer, improving quality for difficult analysis.
        
        For Claude 4 models with tools, uses interleaved thinking beta.
        """
        logger.info(f"[{self.agent_id}] Starting extended thinking call...")
        
        full_text = ""
        thinking_text = ""
        tool_uses = []
        
        # Emit mode changed to thinking
        await self._publish_event_async(
            create_mode_changed_event(self.agent_id, "thinking")
        )
        
        # For Claude 4 with tools, need interleaved thinking beta header
        # Create a new client with beta header for this request
        thinking_client = anthropic.Anthropic(
            default_headers={
                "anthropic-beta": "interleaved-thinking-2025-05-14"
            }
        )
        
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": self.system_prompt,
            "messages": messages,
            "thinking": {
                "type": "enabled",
                "budget_tokens": 5000
            }
        }
        
        if tools:
            kwargs["tools"] = tools
        
        try:
            # Use non-streaming for extended thinking (more reliable)
            response = thinking_client.messages.create(**kwargs)
            
            # Process response content blocks
            for block in response.content:
                if block.type == "thinking":
                    thinking_text = block.thinking
                elif block.type == "text":
                    full_text = block.text
                    await self._publish_event_async(
                        create_thinking_event(self.agent_id, full_text)
                    )
                elif block.type == "tool_use":
                    tool_uses.append({
                        'id': block.id,
                        'name': block.name,
                        'input': block.input
                    })
            
            # Emit thinking complete
            if thinking_text:
                await self._publish_event_async(
                    create_thinking_complete_event(self.agent_id, f"[Extended Thinking Complete]")
                )
            
            return {
                "text": full_text,
                "thinking": thinking_text,
                "tool_uses": tool_uses,
                "stop_reason": response.stop_reason
            }
            
        except anthropic.APIError as e:
            logger.warning(f"Extended thinking failed, falling back to standard: {e}")
            # Fallback to standard call without thinking
            return await self._call_claude_streaming(messages, tools)
    
    async def _call_claude_streaming(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call Claude with streaming enabled."""
        
        # Emit mode changed to streaming
        await self._publish_event_async(
            create_mode_changed_event(self.agent_id, "streaming")
        )
        
        full_text = ""
        tool_uses = []
        current_tool_use = None
        current_tool_input = ""
        
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": self.system_prompt,
            "messages": messages
        }
        
        if tools:
            kwargs["tools"] = tools
        
        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'content_block_start':
                        if hasattr(event, 'content_block'):
                            if event.content_block.type == 'tool_use':
                                current_tool_use = {
                                    'id': event.content_block.id,
                                    'name': event.content_block.name,
                                    'input': {}
                                }
                                current_tool_input = ""
                    
                    elif event.type == 'content_block_delta':
                        if hasattr(event, 'delta'):
                            if hasattr(event.delta, 'text'):
                                chunk = event.delta.text
                                full_text += chunk
                                # Emit thinking event for each chunk
                                await self._publish_event_async(
                                    create_thinking_event(self.agent_id, chunk)
                                )
                            elif hasattr(event.delta, 'partial_json'):
                                current_tool_input += event.delta.partial_json
                    
                    elif event.type == 'content_block_stop':
                        if current_tool_use is not None:
                            try:
                                current_tool_use['input'] = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                current_tool_use['input'] = {}
                            tool_uses.append(current_tool_use)
                            current_tool_use = None
                            current_tool_input = ""
        
        # Emit thinking complete if we had text
        if full_text:
            await self._publish_event_async(
                create_thinking_complete_event(self.agent_id, full_text)
            )
        
        # Safely get stop_reason
        stop_reason = None
        try:
            if hasattr(stream, 'response') and stream.response:
                stop_reason = getattr(stream.response, 'stop_reason', None)
        except Exception:
            pass
        
        return {
            "text": full_text,
            "tool_uses": tool_uses,
            "stop_reason": stop_reason
        }
    
    async def _call_claude_sync(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call Claude without streaming."""
        
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": self.system_prompt,
            "messages": messages
        }
        
        if tools:
            kwargs["tools"] = tools
        
        response = self.client.messages.create(**kwargs)
        
        text = ""
        tool_uses = []
        
        for block in response.content:
            if block.type == "text":
                text = block.text
                await self._publish_event_async(
                    create_thinking_event(self.agent_id, text)
                )
            elif block.type == "tool_use":
                tool_uses.append({
                    'id': block.id,
                    'name': block.name,
                    'input': block.input
                })
        
        return {
            "text": text,
            "tool_uses": tool_uses,
            "stop_reason": response.stop_reason
        }
    
    async def _handle_tool_use(
        self,
        tool_uses: List[Dict[str, Any]],
        code: str
    ) -> List[Dict[str, Any]]:
        """
        Handle tool calls from Claude.
        
        Args:
            tool_uses: List of tool use blocks from Claude
            code: The code being analyzed (for tools that need it)
            
        Returns:
            List of tool results to send back
        """
        results = []
        
        for tool_use in tool_uses:
            tool_call_id = str(uuid.uuid4())
            tool_name = tool_use['name']
            tool_input = tool_use['input']
            
            # Emit tool call start event
            await self._publish_event_async(create_tool_call_start_event(
                self.agent_id,
                tool_call_id,
                tool_name,
                tool_input,
                purpose=f"Executing {tool_name}"
            ))
            
            start_time = time.time()
            
            try:
                # Add code to input if needed
                if 'code' not in tool_input and tool_name in [
                    'parse_ast', 'check_syntax', 'search_pattern',
                    'find_function_calls', 'analyze_imports', 'extract_strings'
                ]:
                    tool_input['code'] = code
                
                # Execute the tool
                result = execute_tool(tool_name, tool_input)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Emit tool call result event
                await self._publish_event_async(create_tool_call_result_event(
                    self.agent_id,
                    tool_call_id,
                    tool_name,
                    result.success,
                    result.output if result.success else None,
                    duration_ms,
                    result.error
                ))
                
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use['id'],
                    "content": json.dumps(result.output) if result.success else f"Error: {result.error}"
                })
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Tool execution error: {e}")
                
                await self._publish_event_async(create_tool_call_result_event(
                    self.agent_id,
                    tool_call_id,
                    tool_name,
                    False,
                    None,
                    duration_ms,
                    str(e)
                ))
                
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use['id'],
                    "content": f"Error executing tool: {e}"
                })
        
        return results
    
    async def _run_agent_loop(
        self,
        initial_prompt: str,
        code: str,
        max_iterations: int = 10,
        use_thinking: bool = False
    ) -> str:
        """
        Run the agent loop with tool use until completion.
        
        Args:
            initial_prompt: The initial prompt to send
            code: The code being analyzed
            max_iterations: Maximum number of tool use iterations
            use_thinking: Whether to use extended thinking for complex analysis
            
        Returns:
            Final text response from the agent
        """
        messages = [{"role": "user", "content": initial_prompt}]
        tools = self.get_tools()
        
        for iteration in range(max_iterations):
            # Use extended thinking on first iteration for deep analysis
            use_thinking_this_iteration = use_thinking and iteration == 0
            response = await self._call_claude(
                messages, 
                tools if tools else None,
                use_streaming=not use_thinking_this_iteration,
                use_thinking=use_thinking_this_iteration
            )
            
            # If no tool use, we're done
            if not response.get('tool_uses'):
                return response.get('text', '')
            
            # Handle tool uses
            tool_results = await self._handle_tool_use(response['tool_uses'], code)
            
            # Build assistant message with content blocks
            # NOTE: Do NOT include thinking blocks in message history - they are internal only
            assistant_content = []
            
            if response.get('text'):
                assistant_content.append({"type": "text", "text": response['text']})
            for tu in response['tool_uses']:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu['id'],
                    "name": tu['name'],
                    "input": tu['input']
                })
            
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        
        logger.warning(f"Agent {self.agent_id} reached max iterations")
        return response.get('text', '')
    
    def _emit_agent_started(self, task: str, input_summary: str = "") -> None:
        """Emit agent started event."""
        self._start_time = time.time()
        event = create_agent_started_event(self.agent_id, task, input_summary)
        self._publish_event(event)
    
    def _emit_agent_completed(self, success: bool, summary: str) -> None:
        """Emit agent completed event."""
        duration_ms = int((time.time() - self._start_time) * 1000) if self._start_time else 0
        event = create_agent_completed_event(
            self.agent_id,
            success,
            len(self._findings),
            len(self._fixes),
            duration_ms,
            summary
        )
        self._publish_event(event)
    
    def reset(self) -> None:
        """Reset the agent's state."""
        self.messages = []
        self._findings = []
        self._fixes = []
        self._start_time = None
