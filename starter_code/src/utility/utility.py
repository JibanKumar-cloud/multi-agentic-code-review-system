import logging
import json
import uuid

from typing import Dict, List, Tuple, Union, Any
from collections import defaultdict
from ..tools import CodeTools
from ..events import (
    Event, EventBus,
    create_mode_changed_event,
    create_tool_call_start_event,
    create_tool_call_result_event,
    create_finding_discovered_event,
    create_fix_proposed_event,
    create_agent_started_event,
    create_agent_completed_event,
    create_fix_verified_event,
    Fix,
    Finding,
    Location
)

logger = logging.getLogger(__name__)

async def emit_agent_finding_fixes(event_bus: EventBus, agent_id: str, finding: Finding, fix: Fix):
    """Emit Finding and Fixed propose event."""
    await event_bus.publish(create_finding_discovered_event(agent_id, finding))
    await event_bus.publish(create_fix_proposed_event(agent_id, fix))

async def emit_agent_started(event_bus: EventBus, agent_id: str, task: str, input_summary: str = "", mode: str=""):
    """Emit agent started event."""
    await event_bus.publish(create_agent_started_event(agent_id=agent_id, task=task, input_summary=input_summary))
    await event_bus.publish(create_mode_changed_event(agent_id=agent_id, mode=mode))

async def emit_agent_completed(event_bus: EventBus, 
                                agent_id: str,
                                success: bool, 
                                findings_count: int,
                                fixes_proposed: int,
                                duration_ms: int,
                                summary: str,
                                mode: str="") -> None:
    """Emit agent completed event."""

    await event_bus.publish(create_agent_completed_event(
            agent_id=agent_id,
            success=success,
            findings_count=findings_count,
            fixes_proposed=fixes_proposed,
            duration_ms=duration_ms,
            summary=summary))
    await event_bus.publish(create_mode_changed_event(agent_id=agent_id, mode=mode))

async def parse_response_to_findings(
    event_bus: EventBus,
    response: Union[str, Dict[str, Any]],
    code: str,
    filename: str,
    agent_id: str,
) -> Dict[List[Finding], List[Fix]]:
    """Parse the agent response (string OR model dict) into Finding and Fix objects."""

    finding_to_fix_map = defaultdict(list)
    # 1) Normalize to text
    if isinstance(response, dict):
        text = response.get("text", "") or ""
    else:
        text = response or ""

    text = text.strip()

    # 2) Remove fenced code blocks if present (```json ... ```)
    if "```" in text:
        # keep the inside of the first fenced block if it looks like JSON
        parts = text.split("```")
        # parts: [before, lang+body, after, ...]
        if len(parts) >= 2:
            fenced = parts[1]
            # drop optional leading 'json'
            fenced = fenced.lstrip()
            if fenced.lower().startswith("json"):
                fenced = fenced[4:].lstrip()
            # fenced ends at next fence split; parts[1] already excludes trailing ```
            # but may include it depending on split; safe strip:
            text = fenced.strip()

    # 3) Choose default IDs/titles
    category = ""
    if agent_id == "bug_agent":
        category == "bug"
        default_title = "Bug Detected"
    elif agent_id == "security_agent":
        category == "sec"
        default_title = "Security Issue"
    else:
        raise Exception(f"This agent is not allowed to call this tool!")

    # 4) Extract JSON object substring (best-effort)
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        raise Exception("Agent: No JSON object found in response text")

    json_str = text[json_start:json_end]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        raise Exception(f"Agent: Failed to parse JSON response: {e}")
    
    code_lines = code.split("\n")

    for item in data.get("findings", []):
        finding_id = item.get("id", f"bug_{uuid.uuid4().hex[:8]}")
        id_step = item["type_id"].split("_")[-1]
        step_id = f"step_{id_step}"

        line_start = int(item.get("line_start", 1))
        line_end = int(item.get("line_end", line_start))

        snippet = item.get("code_snippet", "") or ""
        if not snippet and 1 <= line_start <= len(code_lines):
            snippet = "\n".join(code_lines[line_start - 1: line_end])

        finding = Finding(
            finding_id=finding_id,
            step_id=step_id,
            category=category,
            agent_id=agent_id,
            severity=item.get("severity", "medium"),
            finding_type=item.get("type", "unknown"),
            title=item.get("title", default_title),
            description=item.get("description", ""),
            location=Location(
                file=filename,
                line_start=line_start,
                line_end=line_end,
                code_snippet=snippet
            ),
            confidence=float(item.get("confidence", 0.8)),
        )

        fix_data = item.get("fix", {}) or {}
        proposed = fix_data.get("code")
     

        if proposed:
            fix = Fix(
                fix_id=f"fix_{finding_id}",
                finding_id=finding_id,
                agent_id=agent_id,
                original_code=snippet,
                proposed_code=proposed,
                explanation=fix_data.get("explanation", ""),
                confidence=float(item.get("confidence", 0.8)),
                auto_applicable=True,
            )
            # Verify the fix
            fix, finding = await verify_fix_execute_code(event_bus=event_bus,
                                 agent_id=agent_id,
                                 finding=finding,
                                 fix=fix)
            
            finding_to_fix_map[finding_id].append(finding)
            finding_to_fix_map[finding_id].append(fix)
            await emit_agent_finding_fixes(event_bus, agent_id, finding, fix)

    return finding_to_fix_map


async def verify_fix_execute_code(
        event_bus: EventBus,
        agent_id: str,
        finding: Finding,
        fix: Fix,
    ) -> Tuple[List[Fix], List[Finding]]:
        """Verify proposed fixe using static analysis and runtime execution."""

        finding_id = fix.finding_id

        # Step 1: Static analysis verification
        static_tool_id = f"verify_fix_{finding_id}"
        await event_bus.publish(
            create_tool_call_start_event(
                agent_id,
                static_tool_id,
                "verify_fix",
                {"issue_type": finding.finding_type},
                "Static analysis",
            )
        )

        static_result = CodeTools.verify_fix(
            fix.original_code,
            fix.proposed_code,
            finding.finding_type,
        )

        await event_bus.publish(
            create_tool_call_result_event(
                "coordinator",
                static_tool_id,
                "verify_fix",
                static_result.success,
                static_result.output,
                0,
            )
        )

        # Step 2: Runtime verification (syntax check)
        runtime_result = None
        if fix.proposed_code and static_result.success:
            exec_tool_id = f"execute_code_{finding_id}"
            await event_bus.publish(
                create_tool_call_start_event(
                    "coordinator",
                    exec_tool_id,
                    "execute_code",
                    {"timeout": 5},
                    "Runtime check",
                )
            )

            escaped_code = fix.proposed_code.replace('"""', "'''")
            test_code = f'''
try:
    compile("""{escaped_code}""", "<fix>", "exec")
    print("SYNTAX_OK")
except SyntaxError as e:
    print("SYNTAX_ERROR:", e)
'''
            runtime_result = CodeTools.execute_code(test_code, timeout=5)

            await event_bus.publish(
                create_tool_call_result_event(
                    "coordinator",
                    exec_tool_id,
                    "execute_code",
                    runtime_result.success,
                    runtime_result.output,
                    0,
                )
            )

        # Store verification results on the Fix object
        fix.verified = bool(static_result.success)
        fix.verification_result = {
            "static_analysis": static_result.output,
            "runtime_check": runtime_result.output if runtime_result else None,
        }

        if runtime_result and not runtime_result.success:
            fix.verified = False
            fix.verification_result["runtime_error"] = runtime_result.error

        await event_bus.publish(
            create_fix_verified_event(
                "coordinator",
                fix.fix_id,
                finding_id,
                fix.verified,
                "static_and_runtime",
                json.dumps(fix.verification_result),
                0,
            )
        )

        return fix, finding

def parse_plan(response: str, review_id: str) -> Dict[str, Any]:
    """Parse execution plan from response."""
    try:
        data = {}
        import re
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
        
        data["plan_id"] = f"plan_{review_id}"
        return data
    except Exception as e:
        raise Exception(f"Failed to generate LLM plan, using fallback: {e}")

