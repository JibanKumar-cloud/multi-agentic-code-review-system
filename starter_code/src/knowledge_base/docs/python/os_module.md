# Python os Module Documentation

## Official Documentation Reference
Source: https://docs.python.org/3/library/os.html

## Module Purpose
This module provides a portable way of using operating system dependent functionality. It provides functions for interacting with the filesystem, processes, and environment.

## Dangerous Functions

### os.system() - Deprecated for Subprocess
```python
import os

# DANGEROUS - Executes in shell, vulnerable to injection
os.system(f"ls {user_input}")  # Shell injection!
os.system("rm " + filename)     # Shell injection!

# Use subprocess instead (see subprocess module docs)
```

### os.popen() - Deprecated
```python
# DANGEROUS - Also uses shell
output = os.popen(f"cat {filename}").read()  # Shell injection!

# Use subprocess.run() instead
```

### os.exec*() Family - Rarely Needed
```python
# These replace the current process - use carefully
os.execv(path, args)     # Execute with args list
os.execve(path, args, env)  # With custom environment
```

## Path Security

### Path Traversal Prevention
```python
import os

# DANGEROUS - Path traversal possible
def read_file(filename):
    path = os.path.join('/var/data', filename)
    with open(path) as f:
        return f.read()

# Attack: filename = "../../../etc/passwd"
# Results in: /var/data/../../../etc/passwd = /etc/passwd

# SAFE - Validate path stays within base directory
def safe_read_file(filename):
    base_dir = os.path.abspath('/var/data')
    requested = os.path.abspath(os.path.join(base_dir, filename))
    
    # Check if path is under base_dir
    if not requested.startswith(base_dir + os.sep):
        raise ValueError("Path traversal detected")
    
    with open(requested) as f:
        return f.read()
```

### Safe Path Operations
```python
import os

# Path manipulation
os.path.join(dir, file)       # Join paths safely
os.path.abspath(path)         # Get absolute path
os.path.normpath(path)        # Normalize path
os.path.realpath(path)        # Resolve symlinks
os.path.basename(path)        # Get filename
os.path.dirname(path)         # Get directory

# Path checks
os.path.exists(path)          # Path exists?
os.path.isfile(path)          # Is a file?
os.path.isdir(path)           # Is a directory?
os.path.islink(path)          # Is a symlink?
```

## Environment Variables

### Secure Access
```python
import os

# Get environment variable (returns None if not set)
api_key = os.environ.get('API_KEY')

# Get with default
debug = os.environ.get('DEBUG', 'false')

# Required variable (raises KeyError if not set)
database_url = os.environ['DATABASE_URL']
```

### Don't Hardcode Secrets
```python
# WRONG - Hardcoded secret
API_KEY = "sk-1234567890"

# CORRECT - From environment
API_KEY = os.environ.get('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

## File Operations

### Safe File Deletion
```python
import os

# Check before delete
if os.path.exists(filepath) and os.path.isfile(filepath):
    os.remove(filepath)

# Or use try/except
try:
    os.remove(filepath)
except FileNotFoundError:
    pass  # File already deleted
```

### Directory Operations
```python
import os

# Create directory
os.makedirs(path, exist_ok=True)  # Create with parents, no error if exists

# List directory
files = os.listdir(directory)

# Walk directory tree
for root, dirs, files in os.walk(start_path):
    for file in files:
        filepath = os.path.join(root, file)
```

### Secure Temporary Files
```python
import os
import tempfile

# WRONG - Predictable filename
temp_path = '/tmp/myapp_temp.txt'

# CORRECT - Unpredictable, auto-cleaned
with tempfile.NamedTemporaryFile(delete=True) as f:
    f.write(b'data')
    # File deleted when context exits

# Or for directories
with tempfile.TemporaryDirectory() as tmpdir:
    filepath = os.path.join(tmpdir, 'file.txt')
```

## File Permissions

### Set Secure Permissions
```python
import os
import stat

# Create file with restricted permissions (owner only)
fd = os.open('secret.txt', os.O_WRONLY | os.O_CREAT, 0o600)
os.write(fd, b'secret data')
os.close(fd)

# Change permissions of existing file
os.chmod('secret.txt', stat.S_IRUSR | stat.S_IWUSR)  # 0o600
```

### Check Permissions
```python
import os

# Check if readable/writable/executable
os.access(path, os.R_OK)  # Readable?
os.access(path, os.W_OK)  # Writable?
os.access(path, os.X_OK)  # Executable?
```

## Process Information
```python
import os

os.getpid()       # Current process ID
os.getppid()      # Parent process ID
os.getcwd()       # Current working directory
os.chdir(path)    # Change directory
os.getuid()       # User ID (Unix)
os.getgid()       # Group ID (Unix)
```

## Common Security Mistakes

### Mistake 1: Race Conditions (TOCTOU)
```python
import os

# WRONG - Time-of-check to time-of-use race
if os.path.exists(filepath):
    # Attacker could delete file here!
    with open(filepath) as f:
        data = f.read()

# CORRECT - Just try to open
try:
    with open(filepath) as f:
        data = f.read()
except FileNotFoundError:
    data = None
```

### Mistake 2: Symlink Following
```python
import os

# DANGEROUS - Could follow symlink outside base dir
path = os.path.join(base_dir, user_input)
with open(path) as f:
    data = f.read()

# SAFER - Resolve symlinks and check
real_path = os.path.realpath(os.path.join(base_dir, user_input))
if not real_path.startswith(os.path.realpath(base_dir) + os.sep):
    raise ValueError("Path escapes base directory")
```

## pathlib Alternative (Python 3.4+)
```python
from pathlib import Path

# Modern path handling
base = Path('/var/data')
filepath = base / filename

# Check containment
if base.resolve() not in filepath.resolve().parents:
    raise ValueError("Path traversal")

# File operations
filepath.read_text()
filepath.write_text('content')
filepath.exists()
filepath.is_file()
filepath.unlink()  # Delete
```

## References
- https://docs.python.org/3/library/os.html
- https://docs.python.org/3/library/os.path.html
- https://docs.python.org/3/library/pathlib.html
