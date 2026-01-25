"""
Bug Detection Agent - Specializes in finding logic bugs and runtime errors.
"""

from typing import Any, Dict, List, Optional
import json
import uuid
import logging

from .base_agent import BaseAgent
from ..config import config
from ..events import (
    EventBus, Finding, Fix, Location,
    create_finding_discovered_event,
    create_fix_proposed_event,
)
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
        return """You are a Bug Detection Agent - an expert at finding logic errors, runtime bugs, and potential crashes in Python code.

Your primary focus areas:
1. **Null/None References**: Accessing attributes/methods on potentially None values
2. **Type Errors**: Calling methods that don't exist, wrong argument types  
3. **Logic Errors**: Off-by-one bugs, incorrect conditions, wrong operators
4. **Race Conditions**: Unsynchronized access to shared state in concurrent code
5. **Resource Leaks**: Files/connections not properly closed
6. **Error Handling**: Bare except, swallowed exceptions, missing error handling
7. **Division by Zero**: Operations that could divide by zero
8. **Index Errors**: Array/list access that could be out of bounds

For EACH bug found, you MUST provide:
- Exact line numbers where the issue occurs
- Severity (critical, high, medium, low)
- Clear description of the bug and when it would occur
- A concrete fix with actual code

Output your findings in this JSON format:
{
    "findings": [
        {
            "id": "unique_id",
            "category": "bug",
            "severity": "critical|high|medium|low",
            "type": "null_reference|type_error|logic_error|race_condition|resource_leak|error_handling|division_by_zero|index_error",
            "title": "Short descriptive title",
            "description": "Detailed explanation of the bug and when it would manifest",
            "line_start": 42,
            "line_end": 43,
            "code_snippet": "the buggy code",
            "fix": {
                "code": "the corrected code",
                "explanation": "why this fixes the issue"
            },
            "confidence": 0.9
        }
    ],
    "summary": "Brief summary of code quality"
}

Be thorough but avoid false positives. Focus on bugs that would actually cause runtime errors or incorrect behavior.
Use the available tools to analyze the code structure when needed."""
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Bug detection tools."""
        return [
            t for t in TOOL_DEFINITIONS 
            if t['name'] in [
                'parse_ast', 'search_pattern', 'find_function_calls',
                'analyze_imports', 'get_line_context', 'check_syntax'
            ]
        ]
    
    async def analyze(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze code for bugs.
        
        Args:
            code: The Python code to analyze
            context: Optional context (filename, etc.)
            
        Returns:
            Dictionary with findings and fixes
        """
        filename = context.get('filename', 'unknown.py') if context else 'unknown.py'
        lines = code.count('\n') + 1
        
        self._emit_agent_started(
            "Bug detection analysis",
            f"{filename} - {lines} lines"
        )
        
        try:
            prompt = f"""Analyze this Python code for bugs and potential runtime errors:

```python
{code}
```

File: {filename}

Look specifically for:
1. None/null reference errors (calling methods on potentially None values)
2. Type errors (wrong types, missing attributes)
3. Logic errors (off-by-one, wrong conditions)
4. Race conditions (if threading/async is used)
5. Resource leaks (unclosed files, connections)
6. Error handling issues (bare except, swallowed errors)
7. Division by zero possibilities
8. Index out of bounds errors

Use the tools to analyze the AST, search for patterns, and examine specific code sections.

After your analysis, provide your findings in the JSON format specified."""
            
            # Run the agent loop with extended thinking for deep bug analysis
            response = await self._run_agent_loop(prompt, code, use_thinking=True)
            
            findings, fixes = self._parse_response(response, filename, code)
            
            for finding in findings:
                await self._publish_event_async(
                    create_finding_discovered_event(self.agent_id, finding)
                )
            
            for fix in fixes:
                await self._publish_event_async(
                    create_fix_proposed_event(self.agent_id, fix)
                )
            
            self._findings = [f.to_dict() for f in findings]
            self._fixes = [f.to_dict() for f in fixes]
            
            self._emit_agent_completed(
                True,
                f"Found {len(findings)} potential bugs"
            )
            
            return {
                "agent": self.agent_id,
                "findings": self._findings,
                "fixes": self._fixes,
                "summary": f"Bug analysis complete. Found {len(findings)} issues."
            }
            
        except Exception as e:
            logger.error(f"Bug agent error: {e}")
            self._emit_agent_completed(False, f"Error: {str(e)}")
            return {
                "agent": self.agent_id,
                "findings": [],
                "fixes": [],
                "error": str(e)
            }
    
    def _parse_response(
        self,
        response: str,
        filename: str,
        code: str
    ) -> tuple[List[Finding], List[Fix]]:
        """Parse the agent's response into Finding and Fix objects."""
        findings = []
        fixes = []
        
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                code_lines = code.split('\n')
                
                for item in data.get('findings', []):
                    finding_id = item.get('id', f"bug_{uuid.uuid4().hex[:8]}")
                    line_start = item.get('line_start', 1)
                    line_end = item.get('line_end', line_start)
                    
                    snippet = item.get('code_snippet', '')
                    if not snippet and 1 <= line_start <= len(code_lines):
                        snippet = '\n'.join(code_lines[line_start-1:line_end])
                    
                    finding = Finding(
                        finding_id=finding_id,
                        category="bug",
                        severity=item.get('severity', 'medium'),
                        finding_type=item.get('type', 'unknown'),
                        title=item.get('title', 'Bug Detected'),
                        description=item.get('description', ''),
                        location=Location(
                            file=filename,
                            line_start=line_start,
                            line_end=line_end,
                            code_snippet=snippet
                        ),
                        confidence=item.get('confidence', 0.8)
                    )
                    findings.append(finding)
                    
                    fix_data = item.get('fix', {})
                    if fix_data and fix_data.get('code'):
                        fix = Fix(
                            fix_id=f"fix_{finding_id}",
                            finding_id=finding_id,
                            original_code=snippet,
                            proposed_code=fix_data.get('code', ''),
                            explanation=fix_data.get('explanation', ''),
                            confidence=item.get('confidence', 0.8),
                            auto_applicable=True
                        )
                        fixes.append(fix)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            findings.extend(self._parse_text_response(response, filename, code))
        
        return findings, fixes
    
    def _parse_text_response(
        self,
        response: str,
        filename: str,
        code: str
    ) -> List[Finding]:
        """Fallback parser for non-JSON responses."""
        findings = []
        
        bug_keywords = {
            'none': 'null_reference',
            'null': 'null_reference',
            'attributeerror': 'null_reference',
            'typeerror': 'type_error',
            'type error': 'type_error',
            'off-by-one': 'logic_error',
            'logic error': 'logic_error',
            'race condition': 'race_condition',
            'resource leak': 'resource_leak',
            'file not closed': 'resource_leak',
            'exception': 'error_handling',
            'bare except': 'error_handling',
            'division by zero': 'division_by_zero',
            'zerodivision': 'division_by_zero',
            'index': 'index_error',
            'indexerror': 'index_error'
        }
        
        response_lower = response.lower()
        
        for keyword, bug_type in bug_keywords.items():
            if keyword in response_lower:
                import re
                line_matches = re.findall(r'line\s*(\d+)', response_lower)
                line_start = int(line_matches[0]) if line_matches else 1
                
                finding = Finding(
                    finding_id=f"bug_{uuid.uuid4().hex[:8]}",
                    category="bug",
                    severity="medium",
                    finding_type=bug_type,
                    title=f"Potential {bug_type.replace('_', ' ').title()}",
                    description=f"Detected potential {keyword} issue",
                    location=Location(
                        file=filename,
                        line_start=line_start,
                        line_end=line_start,
                        code_snippet=""
                    ),
                    confidence=0.6
                )
                findings.append(finding)
        
        return findings
