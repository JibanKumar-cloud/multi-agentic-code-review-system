"""
Code analysis and execution tools for agents.

These tools are available for agents to use during analysis.
"""

import ast
import os
from typing import Any, Dict, Optional
import subprocess
import tempfile


def read_file(path: str) -> str:
    """
    Read contents of a file.

    Args:
        path: Path to the file

    Returns:
        File contents as string
    """
    with open(path, 'r') as f:
        return f.read()


def execute_code(
    code: str,
    timeout: int = 30,
    capture_output: bool = True
) -> Dict[str, Any]:
    """
    Execute Python code in a sandboxed environment.

    SECURITY NOTE: This should be properly sandboxed in production.
    For this assessment, basic subprocess isolation is acceptable.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds
        capture_output: Whether to capture stdout/stderr

    Returns:
        Dictionary with execution results
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['python', temp_path],
            capture_output=capture_output,
            timeout=timeout,
            text=True
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Execution timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        os.unlink(temp_path)


def parse_python_ast(code: str) -> Dict[str, Any]:
    """
    Parse Python code into AST and extract structure.

    Args:
        code: Python code to parse

    Returns:
        Dictionary with code structure information
    """
    try:
        tree = ast.parse(code)

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": [arg.arg for arg in node.args.args]
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(f"{node.module}")

        return {
            "success": True,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "line_count": len(code.split('\n'))
        }

    except SyntaxError as e:
        return {
            "success": False,
            "error": f"Syntax error: {e}"
        }


def get_line_range(code: str, start: int, end: int) -> str:
    """
    Extract a range of lines from code.

    Args:
        code: Full code string
        start: Start line (1-indexed)
        end: End line (1-indexed, inclusive)

    Returns:
        Extracted code lines
    """
    lines = code.split('\n')
    return '\n'.join(lines[start-1:end])


def find_pattern(code: str, pattern: str) -> list:
    """
    Find occurrences of a pattern in code.

    Args:
        code: Code to search
        pattern: Pattern to find

    Returns:
        List of matches with line numbers
    """
    import re

    matches = []
    lines = code.split('\n')

    for i, line in enumerate(lines, 1):
        if re.search(pattern, line):
            matches.append({
                "line": i,
                "content": line.strip()
            })

    return matches


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "execute_code",
        "description": "Execute Python code and return the result",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "parse_python_ast",
        "description": "Parse Python code and extract structure (functions, classes, imports)",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to parse"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "find_pattern",
        "description": "Find occurrences of a regex pattern in code",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code to search"
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to find"
                }
            },
            "required": ["code", "pattern"]
        }
    }
]


# Tool execution dispatcher
TOOL_HANDLERS = {
    "read_file": read_file,
    "execute_code": execute_code,
    "parse_python_ast": parse_python_ast,
    "find_pattern": find_pattern,
    "get_line_range": get_line_range
}


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """
    Execute a tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Input parameters

    Returns:
        Tool result
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return handler(**tool_input)
    except Exception as e:
        return {"error": str(e)}
