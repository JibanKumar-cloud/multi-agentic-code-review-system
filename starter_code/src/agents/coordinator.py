"""
Coordinator Agent - Orchestrates the multi-agent code review.
"""

from typing import Any, Dict, List, Optional
import time
import logging

from ..agents.state import ReviewState
from .base_agent import BaseAgent
from ..config import config

from ..events import (
    EventBus, PlanStep,
    create_plan_created_event,
    create_plan_step_started_event,
    create_plan_step_completed_event,
    create_mode_changed_event,
    create_findings_consolidated_event,
    create_final_report_event)
from ..utility import parse_plan, emit_agent_started, emit_agent_completed
from ..tools import CodeTools

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """
    Coordinator agent that orchestrates the code review process.
    
    Responsibilities:
    - Create analysis plan
    - Delegate to specialist agents
    - Consolidate findings
    - Manage fix verification workflow
    - Generate final report
    """
    
    def __init__(self, event_bus: EventBus):
        super().__init__(
            agent_id="coordinator",
            agent_type="coordinator",
            agent_config=config.coordinator_config,
            event_bus=event_bus
        )
    
        self._current_plan: Optional[Dict[str, Any]] = None
        self._all_findings: List[Dict[str, Any]] = []
        self._all_fixes: List[Dict[str, Any]] = []
        self._review_id: str = ""
    
    @property
    def system_prompt(self) -> str:
        pass

        
    def get_prompt(self, state: ReviewState) -> str:
        # Analysing Code
        code = state["code"]
        filename = state["filename"]
        ast_result = CodeTools.parse_ast(code)
        imports_result = CodeTools.analyze_imports(code)
        
        functions = ast_result.output.get('functions', []) if ast_result.success else []
        imports = ast_result.output.get('imports', []) if ast_result.success else []
        line_count = len(code.split('\n'))
        dangerous_imports = imports_result.output.get('potentially_dangerous', []) if imports_result.success else []
        prompt = f"""You are a Coordinator Agent responsible for orchestrating a multi-agent code review system.

Your responsibilities:
1. Analyze submitted code to understand its structure and purpose
2. Create an analysis plan determining which specialists to involve
3. Consolidate findings from all agents
4. Remove duplicates and merge related findings
5. Prioritize by severity
6. Generate a comprehensive final report

You coordinate the Security Agent and Bug Detection Agent. Always ensure thorough analysis while avoiding redundant work.

**Code Info:**
- File: {filename}
- Lines: {line_count}
- Functions: {', '.join(functions) if functions else 'None detected'}
- Imports: {', '.join(imports[:10]) if imports else 'None'}
- Dangerous imports: {', '.join(d.get('module', '') for d in dangerous_imports) if dangerous_imports else 'None'}

**Available Agents:**
1. security:- Finds SQL injection, XSS, command injection, 
              hardcoded secrets, insecure deserialization
2. bug:- Finds null references, race conditions, Division by zero, logic errors, 
         type errors, error handling issues, Index out of bounds errors
OR you can add your one discovered focus area to look for agent.

**Your Task:**
Create an analysis plan. Respond with JSON only:

```json
{{
    "analysis_summary": "Brief description of what you see in this code",
    "risk_level": "low|medium|high|critical",
    "steps": [
        {{
            "step_id": "step_1",
            "agent": "security",
            "description": "What this step will check",
            "focus_areas": ["specific", "things", "to check"],
            "priority": 1
        }}
    ]
}}
```

Include steps for both security and bug agents if needed. Agent must be either "security" or "bug" based on task. 
Be specific about what each should focus on based on the code as summary."""
        return [{"role": "user", "content": prompt}]

    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Coordinator tools."""
        return []  # Coordinator primarily orchestrates, doesn't need analysis tools
    
    async def analyze(self, state: ReviewState) -> Dict[str, Any]:
        """
        Orchestrate the full code analysis.
        """
        
        if state.get("phase") == "planning" and state.get("bug_agent_completed") and state.get("security_agent_completed"):
            # flip phase via returned update
            if state.get("plan"):  # ensure planning already created a plan
                return await self._coordinator_consolidating({**state, "phase": "consolidating"})
        return await self._coordinator_planning(state)
    
    
    async def _coordinator_planning(self, state: ReviewState) -> Dict[str, Any]:
        """Create a detailed analysis plan using Claude LLM."""

        # Getting Prompt
        messages = self.get_prompt(state)

        # Emiting Agent Starting Events
        await emit_agent_started(self.event_bus, self.agent_id, "Creating execution plan", state["filename"], "thinking") 
   
        # Ask Claude to generate the execution plan
        try:
            # Call Claude to generate the plan
            response =  await self._call_claude(messages=messages, 
                                                agent_id=self.agent_id, 
                                                code="",
                                                tools=None,  
                                                agent_run_mode="streaming")

            # Parse the response
            response_text = response["text"]
            plan = parse_plan(response_text, state["review_id"])

            # Build steps from Claude's plan
            # Emit plan to UI
            plan_steps = []
            for i, s in enumerate(plan.get("steps", [])):
                plan_steps.append(
                    PlanStep(
                    step_id=s.get("step_id", f"step_{i}"),
                    description=s.get("description", "Analysis"),
                    agent=s.get("agent", "coordinator"),
                    status="pending")
                )
                state["step_ids"].add(s["step_id"])
            

            await self.event_bus.publish(create_plan_created_event(plan["plan_id"], plan_steps))
            await self.event_bus.publish(create_mode_changed_event(self.agent_id, ""))
            return {"plan": plan, "phase":"planning"}

        except Exception as e:
            logger.warning(f"Failed to generate LLM plan : {e}")
            return {}
      
   
    async def _coordinator_consolidating(self, state: ReviewState) -> ReviewState:
        """
        Coordinator Consolidating Phase:
        - Merge findings from security + bug agents
        - Deduplicate
        - Emit final findings to UI
        """
        plan_id = state["plan"]["plan_id"]
        
        await self.event_bus.publish(create_mode_changed_event(self.agent_id, "thinking"))
  
        all_findings = state["security_findings"] + state["bug_findings"]
        all_fixes = state["security_fixes"] + state["bug_fixes"]
 

        # 3) Metrics
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_category = {"sec": 0, "bug": 0}

        for f in all_findings:
            f_everity = f.severity if f.severity else "medium"
            f_category = f.category if f.category else "bug"

            by_severity[f_everity] = by_severity.get(f_everity) + 1
            by_category[f_category] = by_category.get(f_category) + 1
        
        await self.event_bus.publish(create_findings_consolidated_event(
            len(all_fixes), by_severity, by_category, 0
        ))

        # 4) Creating Final report
        duration_ms = int((time.time() - state["start_time"]) * 1000)
        summary = f"Found {len(all_findings)} issues"
        if by_severity["critical"] > 0:
            summary += f" ({by_severity['critical']} critical)"

        final_findings_json = [f.to_dict() if hasattr(f, "to_dict") else f for f in all_findings]
        final_fixes_json = [fx.to_dict() if hasattr(fx, "to_dict") else fx for fx in all_fixes]

        
        final_report = {
            "review_id": state["review_id"],
            "summary": summary,
            "plan": state["plan"],
            "findings": final_findings_json,
            "fixes": final_fixes_json,
            "metrics": {
                "total_findings": len(final_findings_json),
                "by_severity": by_severity,
                "fixes_proposed": len(final_fixes_json),
                "duration_ms": duration_ms
            }
        }


        # Completion events
        # await self.event_bus.publish(create_plan_step_completed_event(plan_id, "step_3", "coordinator", True, duration_ms))
        for f in all_findings:
            if f.step_id in state["step_ids"]:
                agent = "coordinator"
                agent = "secure" if f.agent_id == "secure_agent" else "bug"
                await self.event_bus.publish(create_plan_step_started_event(plan_id, f.step_id, agent))
                await self.event_bus.publish(create_plan_step_completed_event(plan_id, f.step_id, agent, True, duration_ms))

        await self.event_bus.publish(create_final_report_event(
            state["review_id"], "completed", summary, final_findings_json, final_fixes_json,
            {"total": len(final_findings_json), "by_severity": by_severity, "fixes_proposed": len(final_fixes_json), "duration_ms": duration_ms}
        ))

        # Emiting Agent Completion Events
        await emit_agent_completed(
                        event_bus=self.event_bus,
                        agent_id=self.agent_id,
                        success=True, 
                        findings_count=len(final_findings_json),
                        fixes_proposed=len(final_fixes_json),
                        duration_ms=duration_ms,
                        summary=f"Found {len(final_findings_json)} issues")

        return {"final_findings": all_findings,
                "final_fixes": all_fixes,
                "final_report": final_report,
                "phase": "done"}



            
        



    
    
