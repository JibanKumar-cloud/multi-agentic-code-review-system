# Python Common Vulnerabilities & Fixes

## Overview
A comprehensive guide to common security vulnerabilities in Python code and their fixes.

---

## 1. Null Reference / NoneType Errors

### Vulnerable Patterns
```python
# VULNERABLE - No None check
def get_user_email(user):
    return user.email.lower()  # Crashes if user is None or email is None

# VULNERABLE - Chained access
def get_city(user):
    return user.profile.address.city  # Multiple potential None points

# VULNERABLE - Dict access without .get()
config = load_config()
timeout = config['timeout']  # KeyError if missing
```

### Fixes
```python
# SECURE - Explicit None check
def get_user_email(user):
    if user is None or user.email is None:
        return None
    return user.email.lower()

# SECURE - Use getattr with default
def get_city(user):
    return getattr(getattr(getattr(user, 'profile', None), 'address', None), 'city', None)

# SECURE - Use .get() with default
timeout = config.get('timeout', 30)

# SECURE - Optional chaining pattern
from typing import Optional
def safe_get(obj, *attrs, default=None):
    for attr in attrs:
        if obj is None:
            return default
        obj = getattr(obj, attr, None)
    return obj if obj is not None else default
```

---

## 2. Division by Zero

### Vulnerable Patterns
```python
# VULNERABLE - No zero check
def calculate_average(items):
    return sum(items) / len(items)  # ZeroDivisionError if empty

# VULNERABLE - User input in divisor
def calculate_rate(total, count):
    return total / count  # count could be 0
```

### Fixes
```python
# SECURE - Check before division
def calculate_average(items):
    if not items:
        return 0
    return sum(items) / len(items)

# SECURE - Guard clause
def calculate_rate(total, count):
    if count == 0:
        return 0  # or raise ValueError("Count cannot be zero")
    return total / count
```

---

## 3. Race Conditions

### Vulnerable Patterns
```python
# VULNERABLE - Check-then-act
def withdraw(account, amount):
    if account.balance >= amount:  # Check
        time.sleep(0.01)  # Window for race
        account.balance -= amount  # Act
        
# VULNERABLE - Read-modify-write
def increment_counter(counter):
    current = counter.value  # Read
    counter.value = current + 1  # Write (not atomic)
```

### Fixes
```python
# SECURE - Use threading.Lock
import threading

lock = threading.Lock()

def withdraw(account, amount):
    with lock:
        if account.balance >= amount:
            account.balance -= amount
            return True
    return False

# SECURE - Use atomic operations
from threading import Lock

class Counter:
    def __init__(self):
        self._value = 0
        self._lock = Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
```

---

## 4. Path Traversal

### Vulnerable Patterns
```python
# VULNERABLE - User input in file path
def read_file(filename):
    path = os.path.join('/var/data', filename)
    with open(path) as f:
        return f.read()

# Attack: filename = "../../etc/passwd"
```

### Fixes
```python
# SECURE - Validate and resolve path
import os

def read_file(filename):
    base_dir = os.path.abspath('/var/data')
    requested_path = os.path.abspath(os.path.join(base_dir, filename))
    
    # Check if resolved path is under base_dir
    if not requested_path.startswith(base_dir):
        raise ValueError("Invalid path")
    
    with open(requested_path) as f:
        return f.read()

# SECURE - Use pathlib
from pathlib import Path

def read_file(filename):
    base_dir = Path('/var/data').resolve()
    requested_path = (base_dir / filename).resolve()
    
    if base_dir not in requested_path.parents and requested_path != base_dir:
        raise ValueError("Path traversal attempt")
    
    return requested_path.read_text()
```

---

## 5. Insecure Random

### Vulnerable Patterns
```python
# VULNERABLE - random module is not cryptographically secure
import random
token = ''.join(random.choices('abcdef0123456789', k=32))
session_id = random.randint(0, 1000000)
```

### Fixes
```python
# SECURE - Use secrets module
import secrets

token = secrets.token_hex(16)  # 32 character hex string
session_id = secrets.token_urlsafe(16)
otp = secrets.randbelow(1000000)  # Random int 0-999999
```

---

## 6. Logging Sensitive Data

### Vulnerable Patterns
```python
# VULNERABLE - Logging passwords
logger.info(f"User login: {username}, password: {password}")

# VULNERABLE - Logging tokens
logger.debug(f"API request with token: {api_token}")
```

### Fixes
```python
# SECURE - Never log sensitive data
logger.info(f"User login attempt: {username}")

# SECURE - Mask sensitive data
def mask_token(token):
    return token[:4] + '*' * (len(token) - 8) + token[-4:]

logger.debug(f"API request with token: {mask_token(api_token)}")
```

---

## 7. XML External Entity (XXE)

### Vulnerable Patterns
```python
# VULNERABLE - Default XML parsing allows XXE
from xml.etree import ElementTree
tree = ElementTree.parse(user_file)

# VULNERABLE - lxml without restrictions
from lxml import etree
doc = etree.parse(user_file)
```

### Fixes
```python
# SECURE - Disable external entities
from defusedxml import ElementTree
tree = ElementTree.parse(user_file)

# SECURE - lxml with restrictions
from lxml import etree
parser = etree.XMLParser(resolve_entities=False, no_network=True)
doc = etree.parse(user_file, parser)
```

---

## 8. SSRF (Server-Side Request Forgery)

### Vulnerable Patterns
```python
# VULNERABLE - Fetching user-provided URL
import requests
url = request.args.get('url')
response = requests.get(url)  # Could access internal services
```

### Fixes
```python
# SECURE - Validate and restrict URLs
from urllib.parse import urlparse
import ipaddress

ALLOWED_HOSTS = ['api.example.com', 'cdn.example.com']

def safe_fetch(url):
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Invalid scheme")
    
    # Check against allowlist
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Host not allowed")
    
    # Block private IPs
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback:
            raise ValueError("Private IP not allowed")
    except ValueError:
        pass  # Hostname, not IP
    
    return requests.get(url, timeout=5)
```

---

## Quick Reference Table

| Vulnerability | Detection Pattern | Fix |
|---------------|-------------------|-----|
| SQL Injection | f-string + SELECT/INSERT | Parameterized queries |
| Command Injection | os.system, shell=True | subprocess with list |
| XSS | f-string + HTML tags | html.escape() |
| Deserialization | pickle.load, yaml.load | json, yaml.safe_load |
| Hardcoded Secrets | API_KEY =, PASSWORD = | Environment variables |
| Path Traversal | os.path.join + user input | Validate resolved path |
| Null Reference | .method() without check | if x is not None |
| Race Condition | read-modify-write | threading.Lock |
