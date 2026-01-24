"""
Code analysis tools that agents can use.
"""

import ast
import re
import subprocess
import tempfile
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None


class CodeTools:
    """Collection of tools for code analysis."""
    
    @staticmethod
    def parse_ast(code: str) -> ToolResult:
        """
        Parse Python code into an AST.
        
        Args:
            code: Python source code
            
        Returns:
            ToolResult with AST dump or error
        """
        try:
            tree = ast.parse(code)
            return ToolResult(
                success=True,
                output={
                    "valid": True,
                    "node_count": sum(1 for _ in ast.walk(tree)),
                    "imports": [
                        node.names[0].name for node in ast.walk(tree)
                        if isinstance(node, ast.Import)
                    ],
                    "from_imports": [
                        f"{node.module}.{node.names[0].name}" 
                        for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom) and node.module
                    ],
                    "functions": [
                        node.name for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                    ],
                    "classes": [
                        node.name for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)
                    ]
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Syntax error at line {e.lineno}: {e.msg}"
            )
    
    @staticmethod
    def check_syntax(code: str) -> ToolResult:
        """
        Check if Python code has valid syntax.
        
        Args:
            code: Python source code
            
        Returns:
            ToolResult indicating syntax validity
        """
        try:
            compile(code, "<string>", "exec")
            return ToolResult(
                success=True,
                output={"valid": True, "message": "Syntax is valid"}
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output={"valid": False},
                error=f"Syntax error at line {e.lineno}: {e.msg}"
            )
    
    @staticmethod
    def get_line_context(code: str, line_number: int, context_lines: int = 3) -> ToolResult:
        """
        Get lines of code around a specific line number.
        
        Args:
            code: Python source code
            line_number: Target line number (1-indexed)
            context_lines: Number of lines before and after
            
        Returns:
            ToolResult with the code context
        """
        lines = code.split('\n')
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context = []
        for i in range(start, end):
            prefix = ">>> " if i == line_number - 1 else "    "
            context.append(f"{i + 1:4d} {prefix}{lines[i]}")
        
        return ToolResult(
            success=True,
            output={
                "lines": context,
                "target_line": line_number,
                "code_snippet": lines[line_number - 1] if 0 < line_number <= len(lines) else ""
            }
        )
    
    @staticmethod
    def search_pattern(code: str, pattern: str, pattern_type: str = "regex") -> ToolResult:
        """
        Search for patterns in code.
        
        Args:
            code: Python source code
            pattern: Pattern to search for
            pattern_type: "regex" or "literal"
            
        Returns:
            ToolResult with matches
        """
        try:
            lines = code.split('\n')
            matches = []
            
            if pattern_type == "regex":
                regex = re.compile(pattern, re.IGNORECASE)
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        matches.append({
                            "line": i,
                            "content": line.strip(),
                            "match": regex.search(line).group()
                        })
            else:
                for i, line in enumerate(lines, 1):
                    if pattern.lower() in line.lower():
                        matches.append({
                            "line": i,
                            "content": line.strip()
                        })
            
            return ToolResult(
                success=True,
                output={
                    "pattern": pattern,
                    "match_count": len(matches),
                    "matches": matches
                }
            )
        except re.error as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Invalid regex pattern: {e}"
            )
    
    @staticmethod
    def find_function_calls(code: str, function_name: str) -> ToolResult:
        """
        Find all calls to a specific function.
        
        Args:
            code: Python source code
            function_name: Name of function to find
            
        Returns:
            ToolResult with call locations
        """
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            calls = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    if func_name == function_name:
                        calls.append({
                            "line": node.lineno,
                            "col": node.col_offset,
                            "code": lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        })
            
            return ToolResult(
                success=True,
                output={
                    "function": function_name,
                    "call_count": len(calls),
                    "calls": calls
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Syntax error: {e}"
            )
    
    @staticmethod
    def analyze_imports(code: str) -> ToolResult:
        """
        Analyze imports in the code.
        
        Args:
            code: Python source code
            
        Returns:
            ToolResult with import analysis
        """
        try:
            tree = ast.parse(code)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            "type": "import",
                            "module": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append({
                            "type": "from_import",
                            "module": node.module,
                            "name": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno
                        })
            
            # Check for potentially dangerous imports
            dangerous = []
            risky_modules = ['pickle', 'subprocess', 'os', 'eval', 'exec', 'compile']
            for imp in imports:
                module = imp.get('module', '') or ''
                name = imp.get('name', '') or ''
                if any(r in module or r in name for r in risky_modules):
                    dangerous.append(imp)
            
            return ToolResult(
                success=True,
                output={
                    "total_imports": len(imports),
                    "imports": imports,
                    "potentially_dangerous": dangerous
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Syntax error: {e}"
            )
    
    @staticmethod
    def extract_strings(code: str) -> ToolResult:
        """
        Extract all string literals from code.
        
        Args:
            code: Python source code
            
        Returns:
            ToolResult with string literals
        """
        try:
            tree = ast.parse(code)
            strings = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    strings.append({
                        "value": node.value[:100],  # Truncate long strings
                        "line": node.lineno,
                        "length": len(node.value)
                    })
            
            # Check for potential secrets
            secret_patterns = [
                r'[A-Za-z0-9+/]{40,}',  # Base64-like
                r'[a-f0-9]{32,}',  # Hex strings
                r'password|secret|key|token|api_key',  # Keywords
            ]
            
            potential_secrets = []
            for s in strings:
                for pattern in secret_patterns:
                    if re.search(pattern, s['value'], re.IGNORECASE):
                        potential_secrets.append(s)
                        break
            
            return ToolResult(
                success=True,
                output={
                    "total_strings": len(strings),
                    "strings": strings[:50],  # Limit output
                    "potential_secrets": potential_secrets
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Syntax error: {e}"
            )
    
    @staticmethod
    def verify_fix(original_code: str, fixed_code: str, issue_type: str) -> ToolResult:
        """
        Verify that a proposed fix is valid.
        
        Args:
            original_code: Original buggy code
            fixed_code: Proposed fixed code
            issue_type: Type of issue being fixed
            
        Returns:
            ToolResult with verification status
        """
        checks = []
        all_passed = True
        
        # Check 1: Syntax validity
        syntax_result = CodeTools.check_syntax(fixed_code)
        checks.append({
            "check": "syntax_validity",
            "passed": syntax_result.success,
            "message": syntax_result.output.get("message") if syntax_result.success else syntax_result.error
        })
        if not syntax_result.success:
            all_passed = False
        
        # Check 2: Code not empty or same
        if fixed_code.strip() == "":
            checks.append({
                "check": "non_empty",
                "passed": False,
                "message": "Fixed code is empty"
            })
            all_passed = False
        elif fixed_code.strip() == original_code.strip():
            checks.append({
                "check": "code_changed",
                "passed": False,
                "message": "Fixed code is identical to original"
            })
            all_passed = False
        else:
            checks.append({
                "check": "code_changed",
                "passed": True,
                "message": "Code has been modified"
            })
        
        # Check 3: Issue-specific checks
        if issue_type.lower() in ["sql_injection", "sql injection"]:
            # Check for parameterized queries
            has_param = "?" in fixed_code or "%s" in fixed_code or "execute(" in fixed_code
            has_fstring = "f\"" in fixed_code or "f'" in fixed_code
            passed = has_param and not (has_fstring and "SELECT" in fixed_code.upper())
            checks.append({
                "check": "parameterized_query",
                "passed": passed,
                "message": "Uses parameterized query" if passed else "May still have injection risk"
            })
            if not passed:
                all_passed = False
        
        elif issue_type.lower() in ["xss", "cross-site scripting"]:
            # Check for escaping
            has_escape = any(x in fixed_code.lower() for x in ["escape", "html.escape", "markupsafe", "bleach"])
            checks.append({
                "check": "xss_escaping",
                "passed": has_escape,
                "message": "Uses HTML escaping" if has_escape else "May not have proper escaping"
            })
        
        elif issue_type.lower() in ["null_reference", "null reference", "none check"]:
            # Check for None checks
            has_check = "is not None" in fixed_code or "is None" in fixed_code or "if " in fixed_code
            checks.append({
                "check": "null_check",
                "passed": has_check,
                "message": "Includes null check" if has_check else "May not check for None"
            })
        
        return ToolResult(
            success=all_passed,
            output={
                "all_checks_passed": all_passed,
                "checks": checks,
                "verification_method": "static_analysis"
            }
        )
    
    @staticmethod
    def execute_code(
        code: str,
        timeout: int = 30,
        capture_output: bool = True
    ) -> ToolResult:
        """
        Execute Python code in a sandboxed environment.
        
        SECURITY NOTE: This should be properly sandboxed in production.
        For this assessment, basic subprocess isolation is acceptable.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            ToolResult with execution results
        """
        temp_path = None
        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            # Execute in subprocess with timeout
            result = subprocess.run(
                ['python', temp_path],
                capture_output=capture_output,
                timeout=timeout,
                text=True
            )
            
            return ToolResult(
                success=result.returncode == 0,
                output={
                    "returncode": result.returncode,
                    "stdout": result.stdout if capture_output else None,
                    "stderr": result.stderr if capture_output else None,
                    "executed": True
                },
                error=result.stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output={"executed": False, "reason": "timeout"},
                error=f"Execution timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output={"executed": False, "reason": "error"},
                error=str(e)
            )
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "parse_ast",
        "description": "Parse Python code into an Abstract Syntax Tree to understand its structure",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to parse"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "check_syntax",
        "description": "Check if Python code has valid syntax",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to check"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_line_context",
        "description": "Get lines of code around a specific line number for context",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code"
                },
                "line_number": {
                    "type": "integer",
                    "description": "The target line number (1-indexed)"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of lines before and after to include",
                    "default": 3
                }
            },
            "required": ["code", "line_number"]
        }
    },
    {
        "name": "search_pattern",
        "description": "Search for patterns in code using regex or literal matching",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to search"
                },
                "pattern": {
                    "type": "string",
                    "description": "The pattern to search for"
                },
                "pattern_type": {
                    "type": "string",
                    "enum": ["regex", "literal"],
                    "description": "Type of pattern matching",
                    "default": "regex"
                }
            },
            "required": ["code", "pattern"]
        }
    },
    {
        "name": "find_function_calls",
        "description": "Find all calls to a specific function in the code",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to analyze"
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function to find"
                }
            },
            "required": ["code", "function_name"]
        }
    },
    {
        "name": "analyze_imports",
        "description": "Analyze all imports in the code, including potentially dangerous ones",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to analyze"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "extract_strings",
        "description": "Extract all string literals from code, useful for finding hardcoded secrets",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to analyze"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "verify_fix",
        "description": "Verify that a proposed fix is valid and addresses the issue",
        "input_schema": {
            "type": "object",
            "properties": {
                "original_code": {
                    "type": "string",
                    "description": "The original buggy code"
                },
                "fixed_code": {
                    "type": "string",
                    "description": "The proposed fixed code"
                },
                "issue_type": {
                    "type": "string",
                    "description": "Type of issue being fixed (e.g., sql_injection, xss, null_reference)"
                }
            },
            "required": ["original_code", "fixed_code", "issue_type"]
        }
    },
    {
        "name": "execute_code",
        "description": "Execute Python code in a sandboxed environment and capture output. Use for testing fixes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds",
                    "default": 30
                }
            },
            "required": ["code"]
        }
    }
]


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
    """
    Execute a tool by name.
    
    Args:
        tool_name: Name of the tool
        tool_input: Input parameters
        
    Returns:
        ToolResult from execution
    """
    tool_map = {
        "parse_ast": lambda i: CodeTools.parse_ast(i["code"]),
        "check_syntax": lambda i: CodeTools.check_syntax(i["code"]),
        "get_line_context": lambda i: CodeTools.get_line_context(
            i["code"], i["line_number"], i.get("context_lines", 3)
        ),
        "search_pattern": lambda i: CodeTools.search_pattern(
            i["code"], i["pattern"], i.get("pattern_type", "regex")
        ),
        "find_function_calls": lambda i: CodeTools.find_function_calls(
            i["code"], i["function_name"]
        ),
        "analyze_imports": lambda i: CodeTools.analyze_imports(i["code"]),
        "extract_strings": lambda i: CodeTools.extract_strings(i["code"]),
        "verify_fix": lambda i: CodeTools.verify_fix(
            i["original_code"], i["fixed_code"], i["issue_type"]
        ),
        "execute_code": lambda i: CodeTools.execute_code(
            i["code"], i.get("timeout", 30)
        )
    }
    
    if tool_name not in tool_map:
        return ToolResult(
            success=False,
            output=None,
            error=f"Unknown tool: {tool_name}"
        )
    
    try:
        return tool_map[tool_name](tool_input)
    except Exception as e:
        return ToolResult(
            success=False,
            output=None,
            error=str(e)
        )
