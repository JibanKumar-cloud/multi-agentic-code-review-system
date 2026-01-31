# OWASP A03:2021 - Injection

## Overview
Injection flaws occur when untrusted data is sent to an interpreter as part of a command or query. The attacker's hostile data can trick the interpreter into executing unintended commands or accessing data without proper authorization.

## Category
- **CWE-79**: Cross-site Scripting (XSS)
- **CWE-89**: SQL Injection
- **CWE-78**: OS Command Injection
- **CWE-94**: Code Injection

## Severity
**CRITICAL** - Can lead to complete system compromise, data theft, or data loss.

## Common Patterns in Python

### SQL Injection
```python
# VULNERABLE - String concatenation
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)

# VULNERABLE - Format string
query = "SELECT * FROM users WHERE id = %s" % user_id
cursor.execute(query)
```

### Command Injection
```python
# VULNERABLE - os.system with user input
os.system(f"ping {hostname}")

# VULNERABLE - subprocess with shell=True
subprocess.run(f"ls {directory}", shell=True)
```

## Fixes

### SQL Injection Fix
```python
# SECURE - Parameterized query
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))

# SECURE - Using ORM (SQLAlchemy)
User.query.filter_by(username=username).first()
```

### Command Injection Fix
```python
# SECURE - Use list arguments, no shell
subprocess.run(["ping", "-c", "4", hostname], shell=False)

# SECURE - Use shlex.quote for unavoidable shell
import shlex
subprocess.run(f"ping {shlex.quote(hostname)}", shell=True)
```

## Detection Tips
- Look for f-strings or .format() with SQL keywords (SELECT, INSERT, UPDATE, DELETE)
- Look for os.system(), os.popen(), subprocess with shell=True
- Check for eval(), exec() with user input

## References
- OWASP: https://owasp.org/Top10/A03_2021-Injection/
- CWE-89: https://cwe.mitre.org/data/definitions/89.html
- CWE-78: https://cwe.mitre.org/data/definitions/78.html
