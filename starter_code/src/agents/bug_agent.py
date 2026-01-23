"""
Bug Detection Agent - Finds bugs and code quality issues.

TODO: Implement the bug detection agent.
"""

from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config import config
from ..events import EventBus
from ..events.event_types import create_finding_event


class BugDetectionAgent(BaseAgent):
    """
    Bug detection specialist agent.

    Focuses on:
    - Null/None reference errors
    - Off-by-one errors
    - Resource leaks
    - Race conditions
    - Division by zero
    - Unhandled exceptions
    - Logic errors
    - Type errors

    TODO: Complete the implementation
    """

    # Bug categories this agent detects
    BUG_CATEGORIES = [
        "Null Reference",
        "Off-by-One",
        "Resource Leak",
        "Race Condition",
        "Division by Zero",
        "Unhandled Exception",
        "Logic Error",
        "Type Error",
        "Index Out of Bounds",
        "Infinite Loop"
    ]

    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="bug_agent",
            agent_type="bug",
            agent_config=config.bug_agent_config,
            event_bus=event_bus
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for the bug detection agent."""
        return """You are a Bug Detection Specialist Agent focused on finding bugs and code quality issues.

Your expertise includes:
- Null/None References: Variables that might be None when accessed
- Race Conditions: Concurrent access without proper synchronization
- Resource Leaks: Files, connections, locks not properly closed
- Division by Zero: Potential divide by zero scenarios
- Off-by-One Errors: Loop bounds, array indices
- Logic Errors: Incorrect conditions, wrong operators
- Type Errors: Type mismatches, incorrect casts
- Exception Handling: Unhandled or improperly handled exceptions

For each bug found:
1. Identify the exact location (file, line numbers)
2. Explain the bug and when it would manifest
3. Rate severity based on impact (critical, high, medium, low)
4. Provide a working fix
5. Explain edge cases or scenarios that trigger the bug

Focus on bugs that could cause runtime errors, data corruption, or incorrect behavior.
Avoid reporting style issues or minor improvements unless they could cause bugs.

IMPORTANT: Return findings in structured JSON format."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Tools available to the bug agent."""
        return [
            {
                "name": "trace_data_flow",
                "description": "Trace the flow of a variable through the code to find potential issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "variable_name": {
                            "type": "string",
                            "description": "The variable to trace"
                        },
                        "code": {
                            "type": "string",
                            "description": "The code to analyze"
                        }
                    },
                    "required": ["variable_name", "code"]
                }
            },
            {
                "name": "check_null_safety",
                "description": "Check if a code section properly handles null/None values",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code_section": {
                            "type": "string",
                            "description": "The code to check"
                        }
                    },
                    "required": ["code_section"]
                }
            },
            {
                "name": "analyze_concurrency",
                "description": "Analyze code for race conditions and thread safety issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to analyze"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "propose_fix",
                "description": "Propose a fix for a discovered bug",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "bug": {
                            "type": "object",
                            "description": "The bug to fix"
                        },
                        "code_context": {
                            "type": "string",
                            "description": "Surrounding code context"
                        }
                    },
                    "required": ["bug", "code_context"]
                }
            }
        ]

    async def analyze(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze code for bugs.

        TODO: Implement bug detection:
        1. Emit agent_started event
        2. Parse and understand the code
        3. Check for each bug category
        4. Emit finding_discovered event for each finding
        5. Propose fixes for found bugs
        6. Return structured results

        Args:
            code: The code to analyze
            context: Optional context from coordinator
                    (e.g., security findings to avoid duplication)

        Returns:
            Dictionary with findings and proposed fixes
        """
        self._emit_agent_started("Analyzing code for bugs and issues")

        # TODO: Implement bug detection
        # Use Claude to analyze the code
        # Emit events as findings are discovered
        # Return structured results

        raise NotImplementedError("Implement bug detection analysis")

    def _emit_finding(
        self,
        finding_id: str,
        severity: str,
        category: str,
        title: str,
        description: str,
        line_start: int,
        line_end: int,
        code_snippet: str,
        confidence: float = 1.0
    ) -> None:
        """Helper to emit a finding event."""
        event = create_finding_event(
            agent_id=self.agent_id,
            finding_id=finding_id,
            finding_type="bug",
            severity=severity,
            title=title,
            description=description,
            location={
                "line_start": line_start,
                "line_end": line_end,
                "code_snippet": code_snippet
            },
            confidence=confidence
        )
        event.data["category"] = category
        self._publish_event(event)
