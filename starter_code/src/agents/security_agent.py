"""
Security Specialist Agent - Detects security vulnerabilities.

TODO: Implement the security agent.
"""

from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config import config
from ..events import EventBus
from ..events.event_types import create_finding_event


class SecurityAgent(BaseAgent):
    """
    Security specialist agent for vulnerability detection.

    Focuses on:
    - SQL Injection
    - Command Injection
    - XSS (Cross-Site Scripting)
    - Path Traversal
    - Insecure Deserialization
    - Hardcoded Secrets
    - Weak Cryptography

    TODO: Complete the implementation
    """

    # Security vulnerability categories this agent detects
    VULNERABILITY_CATEGORIES = [
        "SQL Injection",
        "Command Injection",
        "XSS",
        "Path Traversal",
        "Insecure Deserialization",
        "Hardcoded Secrets",
        "Weak Cryptography",
        "SSRF",
        "XXE",
        "Authentication Issues"
    ]

    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="security_agent",
            agent_type="security",
            agent_config=config.security_agent_config,
            event_bus=event_bus
        )

    @property
    def system_prompt(self) -> str:
        """System prompt for the security agent."""
        return """You are a Security Specialist Agent focused on finding security vulnerabilities in code.

Your expertise includes:
- SQL Injection: Look for string concatenation in SQL queries
- Command Injection: Look for os.system, subprocess with shell=True, eval, exec
- XSS: Look for unescaped user input in HTML output
- Path Traversal: Look for user input in file paths without validation
- Insecure Deserialization: Look for pickle.loads, yaml.load without safe_load
- Hardcoded Secrets: Look for API keys, passwords, tokens in source code
- Weak Cryptography: Look for MD5, SHA1 for passwords, weak random

For each vulnerability found:
1. Identify the exact location (file, line numbers)
2. Explain why it's a vulnerability
3. Rate severity (critical, high, medium, low)
4. Provide a specific, working fix
5. Explain how the fix addresses the issue

Be thorough but avoid false positives. If unsure, indicate your confidence level.

IMPORTANT: Return findings in structured JSON format."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """Tools available to the security agent."""
        return [
            {
                "name": "analyze_code_section",
                "description": "Analyze a specific section of code for security issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code_section": {
                            "type": "string",
                            "description": "The code section to analyze"
                        },
                        "line_offset": {
                            "type": "integer",
                            "description": "Line number offset for accurate reporting"
                        },
                        "vulnerability_type": {
                            "type": "string",
                            "description": "Specific vulnerability type to check for"
                        }
                    },
                    "required": ["code_section"]
                }
            },
            {
                "name": "check_secret_patterns",
                "description": "Check code for patterns that look like secrets or credentials",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to check"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "propose_fix",
                "description": "Propose a fix for a discovered vulnerability",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "vulnerability": {
                            "type": "object",
                            "description": "The vulnerability to fix"
                        },
                        "code_context": {
                            "type": "string",
                            "description": "Surrounding code context"
                        }
                    },
                    "required": ["vulnerability", "code_context"]
                }
            }
        ]

    async def analyze(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze code for security vulnerabilities.

        TODO: Implement security analysis:
        1. Emit agent_started event
        2. Parse and understand the code
        3. Check for each vulnerability category
        4. Emit finding_discovered event for each finding
        5. Propose fixes for found vulnerabilities
        6. Return structured results

        Args:
            code: The code to analyze
            context: Optional context from coordinator

        Returns:
            Dictionary with findings and proposed fixes
        """
        self._emit_agent_started("Analyzing code for security vulnerabilities")

        # TODO: Implement security analysis
        # Use Claude to analyze the code
        # Emit events as findings are discovered
        # Return structured results

        raise NotImplementedError("Implement security analysis")

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
            finding_type="security",
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
