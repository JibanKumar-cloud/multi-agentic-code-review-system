"""
Security Agent - Specializes in finding security vulnerabilities.
"""

from typing import Any, Dict, List, Optional
import json
import uuid
import logging
import time

from .base_agent import BaseAgent
from ..agents.state import ReviewState

from ..config import config
from ..events import EventBus


from ..utility import (emit_agent_started,
                        parse_response_to_findings,
                        emit_agent_completed)

from ..tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """
    Security specialist agent that identifies vulnerabilities.
    
    Focuses on:
    - SQL injection
    - XSS vulnerabilities
    - Command injection
    - Hardcoded secrets
    - Insecure deserialization
    - Authentication flaws
    """
    
    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="security_agent",
            agent_type="security",
            agent_config=config.security_config,
            event_bus=event_bus
        )
        self.event_bus = event_bus

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    def get_prompt(self, state: ReviewState) -> List[Dict[str, Any]]:
        """Bug detection tools."""
        code = state["code"]

        steps = "\n"
        count = 1
        plan = state["plan"]
        for plan_step in plan["steps"]:
            type_id = plan_step['step_id'].split('_')[-1]
            if plan_step["agent"] == "security":
                desc = plan_step["description"]
                focus_areas = ','.join(plan_step["focus_areas"])
                steps += f"{count}. {desc} \n"
                steps += f"Potential type error: {focus_areas} \n"
                steps += f"type id: type_{type_id} \n"
                count += 1

            prompt = f"""You are the Security Agent for a code review system.

Your task: Find security vulnerabilities in this code.

```python
{code}
```
Look Specifically For:
{steps}

For EACH vulnerability found, you MUST provide:
- Exact line numbers where the issue occurs
- Severity (critical, high, medium, low)
- Clear description of the vulnerability
- A concrete fix with actual code

you can use tools only if need to analyze, understand and verify the code and proposed code, then return findings as JSON:
```json
{{
    "findings": [
        {{
            "type": "sql_injection|xss|command_injection|hardcoded_secret|insecure_deserialization|path_traversal",
            "type_id": "return a type_id from given description, if type of error can be belongs to this type",
            "severity": "critical|high|medium|low",
            "title": "Short descriptive title",
            "description": "Why this is a vulnerability",
            "line_start": 5,
            "line_end": 5,
            "code_snippet": "the vulnerable code",
            "fix": {{
                "code": "the fixed code",
                "explanation": "why this fixes it"
            }}
        }}
    ]
}}
``` 

Be thorough but avoid false positives. Only report issues you're confident about.
Use the available tools to analyze the code structure when needed."""

        return [{"role": "user", "content": prompt}]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Security-relevant tools."""
        return [
            t for t in TOOL_DEFINITIONS 
            if t['name'] in [
                'parse_ast', 'search_pattern', 'find_function_calls',
                'analyze_imports', 'extract_strings', 'get_line_context', 
                'check_syntax', 'verify_fix', 'execute_code'
            ]
        ]
    
    async def analyze(
        self,
        state: ReviewState
    ) -> Dict[str, Any]:
        """
        Analyze code for security vulnerabilities.
        
        Args:
            code: The Python code to analyze
            context: Optional context (filename, etc.)
            
        Returns:
            Dictionary with findings and fixes
        """
        start_time = time.time()
        code = state["code"]
        filename = state["filename"]

        # Getting Prompt
        messages = self.get_prompt(state)

        # Getting tools
        tools = self.get_tools()
        print(tools)
    
        # Emiting Agent Starting Events
        await emit_agent_started(self.event_bus, self.agent_id, "Security analysis", "", "thinking") 

        try:
    
            # Run the agent loop with extended thinking for deep security analysis
            response =  await self._call_claude(messages=messages,
                                                agent_id=self.agent_id, 
                                                code=code, 
                                                tools=tools)    

            finding_to_fix_map = await parse_response_to_findings(
                                        event_bus=self.event_bus,
                                        response=response, 
                                        code=code,
                                        filename=filename, 
                                        agent_id=self.agent_id)

            findings = [f[0]  for f in finding_to_fix_map.values()]
            fixes = [f[1]  for f in finding_to_fix_map.values()]
            duration_ms = int((time.time() - start_time) * 1000)

            # Emiting Agent Completion Events
            await emit_agent_completed(
                        event_bus=self.event_bus,
                        agent_id=self.agent_id,
                        success=True, 
                        findings_count=len(findings),
                        fixes_proposed=len(fixes),
                        duration_ms=duration_ms,
                        summary=f"Found {len(findings)} issues")

            
            return {
                "security_findings": findings,
                "security_fixes": fixes,
                "security_agent_completed": True}
            
        except Exception as e:
            logger.error(f"Security agent error: {e}")
            emit_agent_completed(self.event_bus, self.agent_id, 
                                 False, 0, 0, 0, f"Security agent error: {str(e)}","")
            return {
                "bug_agent_completed": False,
                "bug_findings": [],
                "bug_fixes": []
            }

    
    