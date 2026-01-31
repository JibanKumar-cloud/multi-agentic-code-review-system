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
    create_final_report_event,
    create_thinking_event,
    create_thinking_complete_event)
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
        
        Flow:
        1. First call: phase="planning" -> creates plan -> returns phase="executing"
        2. Second call: phase="executing" + both agents completed -> consolidate -> done
        """
        
        # Check if we're in executing phase AND both specialist agents have completed
        # This means we've already done planning and agent execution, time to consolidate
        if state.get("phase") == "executing" and state.get("bug_agent_completed") and state.get("security_agent_completed"):
            # Both agents finished, move to consolidation phase
            return await self._coordinator_consolidating({**state, "phase": "consolidating"})
        
        # Otherwise, we're in planning phase - create the execution plan
        return await self._coordinator_planning(state)
    
    
    async def _coordinator_planning(self, state: ReviewState) -> Dict[str, Any]:
        """Create a detailed analysis plan using Claude LLM."""
        import asyncio

        messages = self.get_prompt(state)

        await emit_agent_started(
            self.event_bus,
            self.agent_id,
            "Creating execution plan",
            state["filename"],
            "thinking",
        )

        # Emit thinking events - what the coordinator is analyzing
        await self._emit_planning_thoughts(state)

        response = await self._call_claude(
            messages=messages,
            agent_id=self.agent_id,
            code="",
            tools=None,
            agent_run_mode="streaming",
        )

        # Emit thinking complete
        await self.event_bus.publish(create_thinking_complete_event(
            self.agent_id,
            full_thinking=None,
            duration_ms=0
        ))

        response_text = response.get("text", "") or ""
        plan = parse_plan(response_text, state["review_id"])

        plan_steps: list[PlanStep] = []
        new_step_ids = set(state.get("step_ids", set()))

        for i, s in enumerate(plan.get("steps", [])):
            step_id = s.get("step_id") or f"step_{i+1}"

            plan_steps.append(
                PlanStep(
                    step_id=step_id,
                    description=s.get("description", "Analysis"),
                    agent=s.get("agent", "coordinator"),
                    status="pending",
                )
            )
            new_step_ids.add(step_id)

        await self.event_bus.publish(create_plan_created_event(plan["plan_id"], plan_steps))
        await self.event_bus.publish(create_mode_changed_event(self.agent_id, ""))

        # IMPORTANT: move forward, don't stay in planning
        return {
            "plan": plan,
            "phase": "executing",    
            "step_ids": new_step_ids, 
        }

    async def _emit_planning_thoughts(self, state: ReviewState) -> None:
        """Emit thinking events during planning phase."""
        import asyncio
        
        code = state["code"]
        filename = state["filename"]
        
        # Analyze code structure
        ast_result = CodeTools.parse_ast(code)
        imports_result = CodeTools.analyze_imports(code)
        
        functions = ast_result.output.get('functions', []) if ast_result.success else []
        imports_list = imports_result.output.get('imports', []) if imports_result.success else []
        dangerous_imports = imports_result.output.get('potentially_dangerous', []) if imports_result.success else []
        
        # Extract module names from import dicts
        import_names = []
        for imp in imports_list:
            if isinstance(imp, dict):
                import_names.append(imp.get('module', '') or imp.get('name', ''))
            else:
                import_names.append(str(imp))
        
        # Emit thinking stream
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            f"Analyzing {filename} ({len(code.splitlines())} lines)... "
        ))
        await asyncio.sleep(0.1)
        
        if functions:
            func_names = ', '.join(functions[:5])
            await self.event_bus.publish(create_thinking_event(
                self.agent_id,
                f"Found {len(functions)} functions: {func_names}{'...' if len(functions) > 5 else ''}. "
            ))
            await asyncio.sleep(0.1)
        
        if import_names:
            imp_display = ', '.join([n for n in import_names[:5] if n])
            await self.event_bus.publish(create_thinking_event(
                self.agent_id,
                f"Detected imports: {imp_display}{'...' if len(import_names) > 5 else ''}. "
            ))
            await asyncio.sleep(0.1)
        
        if dangerous_imports:
            modules = [d.get('module', '') or d.get('name', '') for d in dangerous_imports[:3] if isinstance(d, dict)]
            if modules:
                await self.event_bus.publish(create_thinking_event(
                    self.agent_id,
                    f"⚠️ Potentially dangerous: {', '.join(modules)}. "
                ))
                await asyncio.sleep(0.1)
        
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            "Creating execution plan for security and bug agents..."
        ))


      
   
    async def _coordinator_consolidating(self, state: ReviewState) -> ReviewState:
        """
        Coordinator Consolidating Phase:
        - Merge findings from security + bug agents
        - Deduplicate
        - Emit final findings to UI
        """
        import asyncio
        
        plan_id = state["plan"]["plan_id"]
        
        await self.event_bus.publish(create_mode_changed_event(self.agent_id, "thinking"))
        
        # Emit thinking for consolidation
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            "Consolidating findings from all agents... "
        ))
        await asyncio.sleep(0.1)
  
        all_findings = state["security_findings"] + state["bug_findings"]
        all_fixes = state["security_fixes"] + state["bug_fixes"]
        
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            f"Merging {len(state['security_findings'])} security + {len(state['bug_findings'])} bug findings. "
        ))
        await asyncio.sleep(0.1)

        # 3) Metrics
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_category = {"sec": 0, "bug": 0}

        for f in all_findings:
            f_everity = f.severity if f.severity else "medium"
            f_category = f.category if f.category else "bug"

            by_severity[f_everity] = by_severity.get(f_everity) + 1
            by_category[f_category] = by_category.get(f_category) + 1
        
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            f"Severity breakdown: {by_severity['critical']} critical, {by_severity['high']} high, {by_severity['medium']} medium. "
        ))
        await asyncio.sleep(0.1)
        
        await self.event_bus.publish(create_thinking_event(
            self.agent_id,
            "Generating final report..."
        ))
        
        await self.event_bus.publish(create_thinking_complete_event(
            self.agent_id,
            full_thinking=None,
            duration_ms=0
        ))
        
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
        # for f in all_findings:
        #     if f.step_id in state["step_ids"]:
        #         agent = "coordinator"
        #         agent = "secure" if f.agent_id == "secure_agent" else "bug"
        #         await self.event_bus.publish(create_plan_step_started_event(plan_id, f.step_id, agent))
        #         await self.event_bus.publish(create_plan_step_completed_event(plan_id, f.step_id, agent, True, duration_ms))

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



            
        



    
    
