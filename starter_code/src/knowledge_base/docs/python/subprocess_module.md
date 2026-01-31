# Python subprocess Module - Security Best Practices

## Official Documentation Reference
Source: https://docs.python.org/3/library/subprocess.html

## Overview
The subprocess module allows you to spawn new processes, connect to their input/output/error pipes, and obtain their return codes.

## Security Warning (from Python docs)
> **Warning**: Unlike some other popen functions, this implementation will never implicitly call a system shell. This means that all characters, including shell metacharacters, can safely be passed to child processes. If the shell is invoked explicitly, via `shell=True`, it is the application's responsibility to ensure that all whitespace and metacharacters are quoted appropriately to avoid shell injection vulnerabilities.

## Dangerous Patterns

### shell=True with User Input
```python
# DANGEROUS - Shell injection possible
import subprocess

user_input = request.args.get('filename')
subprocess.run(f"cat {user_input}", shell=True)  # VULNERABLE!

# Attack: user_input = "file.txt; rm -rf /"
# Executes: cat file.txt; rm -rf /
```

### os.system() - Always Uses Shell
```python
# DANGEROUS - Always uses shell
import os
os.system(f"echo {user_input}")  # VULNERABLE!
```

## Safe Patterns (Recommended)

### Use List Arguments (No Shell)
```python
# SAFE - No shell interpretation
import subprocess

# Pass arguments as a list
result = subprocess.run(
    ["cat", filename],  # List of arguments
    capture_output=True,
    text=True
)

# Special characters are passed literally, not interpreted
subprocess.run(["echo", user_input])  # Safe even if user_input contains ";"
```

### subprocess.run() - Recommended API
```python
# Modern API (Python 3.5+)
import subprocess

# Basic usage
result = subprocess.run(
    ["ls", "-l", directory],
    capture_output=True,  # Capture stdout and stderr
    text=True,            # Return strings instead of bytes
    check=True,           # Raise exception on non-zero exit
    timeout=30            # Timeout in seconds
)

print(result.stdout)
print(result.returncode)
```

### Input Validation
```python
import subprocess
import re

def safe_filename(filename):
    """Validate filename contains only safe characters."""
    if not re.match(r'^[\w\-. ]+$', filename):
        raise ValueError("Invalid filename")
    return filename

# Use with validation
subprocess.run(["cat", safe_filename(user_input)])
```

### Using shlex for Shell Commands
```python
import subprocess
import shlex

# If shell=True is absolutely required, use shlex.quote()
safe_input = shlex.quote(user_input)
subprocess.run(f"echo {safe_input}", shell=True)

# shlex.quote() adds quotes and escapes special characters
# "hello; rm -rf /" becomes "'hello; rm -rf /'" (literal string)
```

## Function Reference

### subprocess.run()
```python
subprocess.run(
    args,                    # Command and arguments (list or string)
    stdin=None,              # Input to the process
    input=None,              # Input data (bytes or string)
    stdout=None,             # Where to send stdout
    stderr=None,             # Where to send stderr
    capture_output=False,    # Capture stdout/stderr
    shell=False,             # Use shell (DANGEROUS with user input)
    cwd=None,                # Working directory
    timeout=None,            # Timeout in seconds
    check=False,             # Raise on non-zero exit
    encoding=None,           # Encoding for text mode
    errors=None,             # Error handling for text mode
    text=None,               # Text mode (encoding='locale')
    env=None                 # Environment variables
)
```

### subprocess.Popen() - Lower Level
```python
# For more control over the process
process = subprocess.Popen(
    ["long_running_command"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Communicate with process
stdout, stderr = process.communicate(timeout=30)

# Or read incrementally
for line in process.stdout:
    print(line)
```

## Common Mistakes

### Mistake 1: String Instead of List
```python
# WRONG - Requires shell=True to work
subprocess.run("ls -l")  # Error or unexpected behavior

# CORRECT - Use list
subprocess.run(["ls", "-l"])
```

### Mistake 2: Forgetting to Handle Errors
```python
# WRONG - Ignores errors
subprocess.run(["might_fail"])

# CORRECT - Check return code
result = subprocess.run(["might_fail"], capture_output=True)
if result.returncode != 0:
    print(f"Error: {result.stderr}")

# Or use check=True to raise exception
subprocess.run(["might_fail"], check=True)
```

### Mistake 3: Blocking Forever
```python
# WRONG - Could hang forever
subprocess.run(["slow_command"])

# CORRECT - Use timeout
subprocess.run(["slow_command"], timeout=30)
```

## Replacement for Deprecated Functions

| Old (Deprecated) | New (Recommended) |
|------------------|-------------------|
| `os.system(cmd)` | `subprocess.run(cmd, shell=True)` |
| `os.popen(cmd)` | `subprocess.run(cmd, shell=True, capture_output=True)` |
| `subprocess.call()` | `subprocess.run()` |
| `subprocess.check_call()` | `subprocess.run(check=True)` |
| `subprocess.check_output()` | `subprocess.run(capture_output=True, check=True).stdout` |

## References
- https://docs.python.org/3/library/subprocess.html
- https://docs.python.org/3/library/shlex.html#shlex.quote
