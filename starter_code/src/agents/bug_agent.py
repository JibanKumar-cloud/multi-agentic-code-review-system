"""
Bug Detection Agent - Specializes in finding logic bugs and runtime errors.
"""

from typing import Any, Dict, List
import logging
import time

from .base_agent import BaseAgent
from .state import ReviewState
from ..config import config
from ..events import (
    EventBus,
    create_thinking_event,
    create_thinking_complete_event
)

from ..utility.retry_errors import (
    AgentEmptyResponseError,
    AgentInvalidJSONError,
    AgentMissingFieldsError)

from ..utility import (parse_response_to_findings,
                       emit_agent_started,
                       emit_agent_completed)

from ..tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


class BugDetectionAgent(BaseAgent):
    """
    Bug detection specialist agent.
    
    Focuses on:
    - Null/None reference errors
    - Type mismatches
    - Logic errors and off-by-one bugs
    - Race conditions
    - Resource leaks
    - Error handling gaps
    - Division by zero
    """
    
    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="bug_agent",
            agent_type="bug_detection",
            agent_config=config.bug_config,
            event_bus=event_bus
        )

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
            if plan_step["agent"] == "bug":
                desc = plan_step["description"]
                focus_areas = ','.join(plan_step["focus_areas"])
                steps += f"{count}. {desc} \n"
                steps += f"Potential type error: {focus_areas} \n"
                steps += f"type id: type_{type_id} \n"
                count += 1


        prompt = f"""You are the Bug Detection Agent Expert for a code review system.
        Your task: Find bugs and errors in this code. 

```python
{code}
```
Look Specifically For these steps:
{steps}

For EACH bug found, you MUST provide:
- Exact line numbers where the issue occurs
- Severity (critical, high, medium, low)
- Clear description of the bug and when it would occur
- A concrete fix with actual code


you can use tools only if need to analyze, understand and verify the code and proposed code, then return findings as JSON::
```json
{{
    "findings": [
        {{
            "type": "null_reference|type_error|missing_error_handling|resource_leak|logic_error|race_condition",
            "type_id": "return a type_id from given description, if type of error can be belongs to this type",
            "severity": "critical|high|medium|low",
            "title": "Short descriptive title",
            "description": "Why this is a bug",
            "line_start": 10,
            "line_end": 10,
            "code_snippet": "the buggy code",
            "fix": {{
                "code": "the fixed code",
                "explanation": "why this fixes it"
            }}
        }}
    ]
}}
```
Be thorough but avoid false positives. Focus on bugs that would actually cause runtime errors or incorrect behavior.
Use the available tools to analyze the code structure when needed."""
        return [{"role": "user", "content": prompt}]
            
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Bug detection tools."""
        return [
            t for t in TOOL_DEFINITIONS 
            if t['name'] in [
                'parse_ast', 'search_pattern', 'find_function_calls',
                'analyze_imports', 'get_line_context', 'check_syntax', 'verify_fix', 'execute_code'
            ]
        ]
    
    async def analyze(
        self,
        state: ReviewState
    ) -> Dict[str, Any]:
        """
        Analyze code for bugs.
        
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
        

        # Emiting Agent Starting Events
        await emit_agent_started(self.event_bus, self.agent_id, "Bug detection", "Bug detection analysis", "thinking") 
        
        # Emit thinking events - what the agent is analyzing
        await self._emit_thinking_stream(state)
        
        try:
            # raise  AgentEmptyResponseError(str(e))
            
            # Run the agent loop with extended thinking for deep bug analysis
            response =  await self._call_claude(messages=messages, 
                                                agent_id=self.agent_id, 
                                                code=code, 
                                                tools=tools) 

            # Emit thinking complete
            thinking_duration = int((time.time() - start_time) * 1000)
            await self.event_bus.publish(create_thinking_complete_event(
                self.agent_id,
                full_thinking=None,
                duration_ms=thinking_duration
            ))

            finding_to_fix_map = await parse_response_to_findings(
                                        event_bus=self.event_bus,
                                        response=response, 
                                        code=code,
                                        filename=filename, 
                                        agent_id=self.agent_id,
                                        plan_id=state["plan"]["plan_id"])
           
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
                    "bug_findings": findings,
                    "bug_fixes": fixes,
                    "bug_agent_completed": True
                    }
            
        except Exception as e:
            print(f"Error: {e}")
            raise  AgentEmptyResponseError(str(e))

    async def _emit_thinking_stream(self, state: ReviewState) -> None:
        """Emit thinking events to show agent's analysis process."""
        import asyncio
        
        plan = state.get("plan", {})
        code = state["code"]
        
        # Initial thinking
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            "Analyzing code for potential bugs and runtime errors... "
        ))
        await asyncio.sleep(0.1)
        
        # Analyze what we're looking for based on plan
        focus_areas = []
        for step in plan.get("steps", []):
            if step.get("agent") == "bug":
                focus_areas.extend(step.get("focus_areas", []))
        
        if focus_areas:
            await self.event_bus.publish(create_thinking_event(
                self.agent_id,
                f"Focus areas: {', '.join(focus_areas[:5])}. "
            ))
            await asyncio.sleep(0.1)
        
        # Code analysis observations
        code_lower = code.lower()
        observations = []
        
        if ".get(" not in code and "[" in code:
            observations.append("Direct indexing without bounds checking - potential IndexError")
        if "None" in code or "null" in code_lower:
            observations.append("None references detected - checking for null pointer issues")
        if "thread" in code_lower or "async" in code_lower or "lock" in code_lower:
            observations.append("Concurrent code patterns - checking for race conditions")
        if "/" in code and "0" in code:
            observations.append("Division operations found - checking for division by zero")
        if "try" not in code_lower and ("open(" in code or "connect" in code_lower):
            observations.append("I/O operations without error handling detected")
        if ".upper()" in code or ".lower()" in code or ".strip()" in code:
            observations.append("String operations on potentially None values - checking null refs")
        
        for obs in observations[:3]:
            await self.event_bus.publish(create_thinking_event(
                self.agent_id,
                f"{obs}. "
            ))
            await asyncio.sleep(0.1)
        
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            "Running deep bug analysis with tools..."
        ))

    
    
    