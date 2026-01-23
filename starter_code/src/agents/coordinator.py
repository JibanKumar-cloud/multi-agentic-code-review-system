"""
Coordinator Agent - Orchestrates the multi-agent code review.

TODO: Implement the coordinator agent.
"""

from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config import config
from ..events import EventBus, EventType, Event


class CoordinatorAgent(BaseAgent):
    """
    Coordinator agent that orchestrates the code review process.

    Responsibilities:
    - Create analysis plan
    - Delegate to specialist agents
    - Consolidate findings
    - Manage fix verification workflow
    - Generate final report

    TODO: Complete the implementation
    """

    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="coordinator",
            agent_type="coordinator",
            agent_config=config.coordinator_config,
            event_bus=event_bus
        )

        # Track registered specialist agents
        self._specialists: Dict[str, BaseAgent] = {}

        # Current analysis state
        self._current_plan: Optional[Dict[str, Any]] = None
        self._all_findings: List[Dict[str, Any]] = []

    @property
    def system_prompt(self) -> str:
        """System prompt for the coordinator."""
        return """You are a Coordinator Agent responsible for orchestrating a multi-agent code review system.

Your responsibilities:
1. Analyze submitted code to create an analysis plan
2. Delegate security analysis to the Security Agent
3. Delegate bug detection to the Bug Detection Agent
4. Consolidate and deduplicate findings from all agents
5. Prioritize fixes based on severity and impact
6. Verify proposed fixes don't introduce new issues
7. Generate a comprehensive final report

When creating a plan:
- Consider the code's complexity and purpose
- Identify which specialist agents should analyze it
- Define the order of analysis (security often first)

When consolidating findings:
- Remove duplicate findings
- Merge related issues
- Rank by severity (critical > high > medium > low)
- Group by category for readability

Always emit appropriate events so the UI can track progress."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Tools available to the coordinator."""
        return [
            {
                "name": "delegate_to_security_agent",
                "description": "Send code to the security specialist agent for vulnerability analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to analyze"
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific security areas to focus on"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "delegate_to_bug_agent",
                "description": "Send code to the bug detection agent for bug analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to analyze"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context about the code"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "verify_fix",
                "description": "Verify that a proposed fix is correct and doesn't introduce new issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "original_code": {
                            "type": "string",
                            "description": "The original buggy code"
                        },
                        "fixed_code": {
                            "type": "string",
                            "description": "The proposed fix"
                        },
                        "finding": {
                            "type": "object",
                            "description": "The finding being fixed"
                        }
                    },
                    "required": ["original_code", "fixed_code", "finding"]
                }
            }
        ]

    def register_specialist(self, agent_type: str, agent: BaseAgent) -> None:
        """
        Register a specialist agent.

        Args:
            agent_type: Type of specialist (security, bug)
            agent: The agent instance
        """
        self._specialists[agent_type] = agent

    async def analyze(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate the full code analysis.

        TODO: Implement the coordination workflow:
        1. Create analysis plan
        2. Emit plan_created event
        3. Execute plan steps (delegate to specialists)
        4. Collect and consolidate findings
        5. Propose fixes for critical/high severity issues
        6. Verify fixes
        7. Generate final report

        Args:
            code: The code to analyze
            context: Optional additional context

        Returns:
            Complete analysis results with findings and fixes
        """
        self._emit_agent_started("Orchestrating code review")

        # TODO: Implement coordination logic
        # This is the main entry point for the analysis workflow

        raise NotImplementedError("Implement the coordinator's analyze method")

    async def _create_plan(self, code: str) -> Dict[str, Any]:
        """
        Create an analysis plan for the code.

        TODO: Implement plan creation
        - Analyze code characteristics
        - Determine which agents to involve
        - Define analysis order

        Returns:
            Plan dictionary with steps
        """
        raise NotImplementedError("Implement plan creation")

    async def _consolidate_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Consolidate findings from all agents.

        TODO: Implement consolidation
        - Remove duplicates
        - Merge related findings
        - Sort by severity

        Returns:
            Consolidated list of findings
        """
        raise NotImplementedError("Implement finding consolidation")

    async def _verify_fix(
        self,
        original_code: str,
        fixed_code: str,
        finding: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify a proposed fix.

        TODO: Implement fix verification
        - Check if fix addresses the issue
        - Check for new issues introduced
        - Return verification result

        Returns:
            Verification result
        """
        raise NotImplementedError("Implement fix verification")
