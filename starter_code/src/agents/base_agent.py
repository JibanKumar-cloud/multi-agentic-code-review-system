"""
Base agent class that all specialized agents inherit from.

TODO: Implement the base agent with Claude API integration.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import anthropic

from ..config import AgentConfig, config
from ..events import Event, EventBus, EventType
from ..events.event_types import (
    create_agent_started_event,
    create_thinking_event,
    create_tool_call_start_event,
    create_tool_call_result_event
)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides:
    - Claude API client initialization
    - Event publishing helpers
    - Tool execution framework
    - Streaming support

    TODO: Complete the implementation
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

        # Tools available to this agent
        self._tools: List[Dict[str, Any]] = []

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
    async def analyze(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        self.event_bus.publish_sync(event)

    async def _call_claude(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        use_streaming: bool = True,
        use_thinking: bool = False
    ) -> Dict[str, Any]:
        """
        Make a call to Claude API.

        TODO: Implement this method with:
        - Streaming support
        - Extended thinking support
        - Tool use handling
        - Event emission for UI updates

        Args:
            messages: Conversation messages
            tools: Optional tools to enable
            use_streaming: Whether to stream the response
            use_thinking: Whether to enable extended thinking

        Returns:
            The response from Claude
        """
        # TODO: Implement Claude API call with streaming and events
        raise NotImplementedError("Implement _call_claude method")

    async def _handle_tool_use(
        self,
        tool_uses: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Handle tool calls from Claude.

        TODO: Implement tool execution with:
        - Event emission for tool call start/result
        - Error handling
        - Timeout handling

        Args:
            tool_uses: List of tool use blocks from Claude

        Returns:
            List of tool results to send back
        """
        # TODO: Implement tool use handling
        raise NotImplementedError("Implement _handle_tool_use method")

    async def _run_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a specific tool.

        Args:
            tool_name: Name of the tool to run
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result
        """
        # TODO: Implement tool execution dispatch
        raise NotImplementedError("Implement _run_tool method")

    def _emit_thinking(self, chunk: str) -> None:
        """Emit a thinking event."""
        event = create_thinking_event(self.agent_id, chunk)
        self._publish_event(event)

    def _emit_agent_started(self, task: str) -> None:
        """Emit agent started event."""
        event = create_agent_started_event(self.agent_id, self.agent_type, task)
        self._publish_event(event)

    def reset(self) -> None:
        """Reset the agent's conversation history."""
        self.messages = []
