"""
Security Agent - Specializes in finding security vulnerabilities.
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
    
    @property
    def system_prompt(self) -> str:
        return """You are a Security Agent - an expert security analyst specializing in identifying vulnerabilities in Python code.

Your primary focus areas:
1. **SQL Injection**: Look for string concatenation or f-strings in SQL queries
2. **Command Injection**: Check os.system(), subprocess calls with shell=True, eval(), exec()
3. **XSS Vulnerabilities**: Find unescaped user input in HTML output
4. **Hardcoded Secrets**: Detect API keys, passwords, tokens in source code
5. **Insecure Deserialization**: pickle.loads(), yaml.load() without safe loader
6. **Weak Cryptography**: MD5, SHA1 for passwords, hardcoded keys

For EACH vulnerability found, you MUST provide:
- Exact line numbers where the issue occurs
- Severity (critical, high, medium, low)
- Clear description of the vulnerability
- A concrete fix with actual code

Output your findings in this JSON format:
{
    "findings": [
        {
            "id": "unique_id",
            "category": "security",
            "severity": "critical|high|medium|low",
            "type": "sql_injection|xss|command_injection|hardcoded_secret|insecure_deserialization|weak_crypto",
            "title": "Short descriptive title",
            "description": "Detailed explanation of the vulnerability and its impact",
            "line_start": 42,
            "line_end": 43,
            "code_snippet": "the vulnerable code",
            "fix": {
                "code": "the corrected code",
                "explanation": "why this fixes the issue"
            },
            "confidence": 0.95
        }
    ],
    "summary": "Brief summary of security posture"
}

Be thorough but avoid false positives. Only report issues you're confident about.
Use the available tools to analyze the code structure when needed."""
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Security-relevant tools."""
        return [
            t for t in TOOL_DEFINITIONS 
            if t['name'] in [
                'parse_ast', 'search_pattern', 'find_function_calls',
                'analyze_imports', 'extract_strings', 'get_line_context'
            ]
        ]
    
    async def analyze(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze code for security vulnerabilities.
        
        Args:
            code: The Python code to analyze
            context: Optional context (filename, etc.)
            
        Returns:
            Dictionary with findings and fixes
        """
        filename = context.get('filename', 'unknown.py') if context else 'unknown.py'
        lines = code.count('\n') + 1
        
        self._emit_agent_started(
            "Security vulnerability analysis",
            f"{filename} - {lines} lines"
        )
        
        try:
            # Build the analysis prompt
            prompt = f"""Analyze this Python code for security vulnerabilities:

```python
{code}
```

File: {filename}

Look specifically for:
1. SQL injection (string concatenation in queries, f-strings with user input)
2. Command injection (os.system, subprocess with shell=True)
3. XSS vulnerabilities (unescaped HTML output)
4. Hardcoded secrets (API keys, passwords, tokens)
5. Insecure deserialization (pickle, yaml)
6. Weak cryptography (MD5, SHA1 for passwords)

Use the tools to analyze imports, search for dangerous patterns, and examine specific code sections.

After your analysis, provide your findings in the JSON format specified."""
            
            # Run the agent loop with extended thinking for deep security analysis
            response = await self._run_agent_loop(prompt, code, use_thinking=True)
            
            # Parse findings from response
            findings, fixes = self._parse_response(response, filename, code)
            
            # Emit events for each finding
            for finding in findings:
                await self._publish_event_async(
                    create_finding_discovered_event(self.agent_id, finding)
                )
            
            # Emit events for each fix
            for fix in fixes:
                await self._publish_event_async(
                    create_fix_proposed_event(self.agent_id, fix)
                )
            
            self._findings = [f.to_dict() for f in findings]
            self._fixes = [f.to_dict() for f in fixes]
            
            self._emit_agent_completed(
                True,
                f"Found {len(findings)} security issues"
            )
            
            return {
                "agent": self.agent_id,
                "findings": self._findings,
                "fixes": self._fixes,
                "summary": f"Security analysis complete. Found {len(findings)} vulnerabilities."
            }
            
        except Exception as e:
            logger.error(f"Security agent error: {e}")
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
        
        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                code_lines = code.split('\n')
                
                for item in data.get('findings', []):
                    finding_id = item.get('id', f"sec_{uuid.uuid4().hex[:8]}")
                    line_start = item.get('line_start', 1)
                    line_end = item.get('line_end', line_start)
                    
                    # Get code snippet
                    snippet = item.get('code_snippet', '')
                    if not snippet and 1 <= line_start <= len(code_lines):
                        snippet = '\n'.join(code_lines[line_start-1:line_end])
                    
                    finding = Finding(
                        finding_id=finding_id,
                        category="security",
                        severity=item.get('severity', 'medium'),
                        finding_type=item.get('type', 'unknown'),
                        title=item.get('title', 'Security Issue'),
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
                    
                    # Create fix if provided
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
            # Try to extract findings from non-JSON response
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
        
        # Look for common vulnerability patterns mentioned
        vulnerability_keywords = {
            'sql injection': 'sql_injection',
            'xss': 'xss',
            'cross-site scripting': 'xss',
            'command injection': 'command_injection',
            'hardcoded': 'hardcoded_secret',
            'secret': 'hardcoded_secret',
            'api key': 'hardcoded_secret',
            'password': 'hardcoded_secret',
            'insecure deserialization': 'insecure_deserialization',
            'pickle': 'insecure_deserialization',
            'md5': 'weak_crypto',
            'weak hash': 'weak_crypto'
        }
        
        response_lower = response.lower()
        
        for keyword, vuln_type in vulnerability_keywords.items():
            if keyword in response_lower:
                # Try to find line numbers
                import re
                line_matches = re.findall(r'line\s*(\d+)', response_lower)
                line_start = int(line_matches[0]) if line_matches else 1
                
                finding = Finding(
                    finding_id=f"sec_{uuid.uuid4().hex[:8]}",
                    category="security",
                    severity="high",
                    finding_type=vuln_type,
                    title=f"Potential {vuln_type.replace('_', ' ').title()}",
                    description=f"Detected potential {keyword} vulnerability",
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
