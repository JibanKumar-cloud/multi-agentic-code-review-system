# CWE-78: OS Command Injection

## Definition
The software constructs all or part of an OS command using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended OS command.

## Severity
**CRITICAL** (CVSS 9.8)

## Alternate Names
- Shell Injection
- Command Injection
- OS Command Injection

## Vulnerable Code Examples

### Python - os.system()
```python
# VULNERABLE
hostname = request.form['hostname']
os.system(f"ping -c 4 {hostname}")

# Attack: hostname = "google.com; cat /etc/passwd"
# Executes: ping -c 4 google.com; cat /etc/passwd
```

### Python - os.popen()
```python
# VULNERABLE
filename = request.args.get('file')
output = os.popen(f"cat {filename}").read()

# Attack: filename = "/etc/passwd; rm -rf /"
```

### Python - subprocess with shell=True
```python
# VULNERABLE
user_input = request.form['cmd']
result = subprocess.run(f"echo {user_input}", shell=True, capture_output=True)

# VULNERABLE - Even with list, shell=True is dangerous
subprocess.run(["sh", "-c", f"ls {directory}"])
```

### Python - subprocess.call/check_output
```python
# VULNERABLE
path = request.args.get('path')
subprocess.call(f"ls -la {path}", shell=True)
subprocess.check_output(f"du -sh {path}", shell=True)
```

### Python - eval/exec
```python
# VULNERABLE - Code injection (related)
expression = request.form['calc']
result = eval(expression)

# Attack: expression = "__import__('os').system('rm -rf /')"
```

## Secure Code Examples

### Use List Arguments (No Shell)
```python
# SECURE - subprocess with list, no shell
hostname = request.form['hostname']
result = subprocess.run(["ping", "-c", "4", hostname], capture_output=True)
# Special characters are treated as literal arguments
```

### Input Validation
```python
# SECURE - Whitelist validation
import re

hostname = request.form['hostname']
if not re.match(r'^[a-zA-Z0-9.-]+$', hostname):
    raise ValueError("Invalid hostname")
    
subprocess.run(["ping", "-c", "4", hostname])
```

### shlex.quote() for Unavoidable Shell
```python
# SECURE - If shell=True is absolutely required
import shlex

filename = request.form['filename']
safe_filename = shlex.quote(filename)
subprocess.run(f"cat {safe_filename}", shell=True, capture_output=True)
# shlex.quote escapes special characters
```

### Use Python Libraries Instead
```python
# SECURE - Use Python libraries instead of shell commands

# Instead of: os.system(f"ping {host}")
import ping3
ping3.ping(host)

# Instead of: subprocess.run(f"ls {path}", shell=True)
import os
files = os.listdir(path)

# Instead of: os.system(f"rm {file}")
import os
os.remove(file)

# Instead of: subprocess.run(f"cp {src} {dst}", shell=True)
import shutil
shutil.copy(src, dst)
```

## Common Attack Patterns
1. **Command Chaining**: `; command2`
2. **Pipe**: `| malicious_command`
3. **Background Execution**: `& malicious_command`
4. **Command Substitution**: `$(malicious_command)` or `` `malicious_command` ``
5. **Newline Injection**: `%0a malicious_command`

## Shell Metacharacters to Watch
```
; | & $ ` ( ) { } [ ] < > " ' \ ! # * ? ~
```

## Detection Patterns
- `os.system(` with f-string or variable
- `os.popen(` with user input
- `subprocess.` with `shell=True`
- `eval(` or `exec(` with external input

## References
- https://cwe.mitre.org/data/definitions/78.html
- https://owasp.org/www-community/attacks/Command_Injection
- https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
