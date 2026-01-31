# OWASP A02:2021 - Cryptographic Failures

## Overview
Failures related to cryptography which often leads to sensitive data exposure. This includes using weak or broken cryptographic algorithms, improper key management, and transmitting data in clear text.

## Category
- **CWE-327**: Use of Broken/Risky Crypto Algorithm
- **CWE-328**: Reversible One-Way Hash
- **CWE-916**: Insufficient Password Hash Complexity

## Severity
**HIGH** - Can lead to credential theft, data exposure, compliance violations.

## Common Patterns in Python

### Weak Hashing for Passwords
```python
# VULNERABLE - MD5 is cryptographically broken
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()

# VULNERABLE - SHA1 is weak for passwords
password_hash = hashlib.sha1(password.encode()).hexdigest()

# VULNERABLE - No salt
password_hash = hashlib.sha256(password.encode()).hexdigest()
```

### Hardcoded Secrets
```python
# VULNERABLE - API key in source code
API_KEY = "sk-1234567890abcdef"

# VULNERABLE - Database password in code
DB_PASSWORD = "supersecretpassword"

# VULNERABLE - JWT secret hardcoded
JWT_SECRET = "my-jwt-secret-key"
```

## Fixes

### Secure Password Hashing
```python
# SECURE - Use bcrypt
import bcrypt
salt = bcrypt.gensalt()
password_hash = bcrypt.hashpw(password.encode(), salt)

# SECURE - Use argon2
from argon2 import PasswordHasher
ph = PasswordHasher()
password_hash = ph.hash(password)

# SECURE - Use passlib
from passlib.hash import pbkdf2_sha256
password_hash = pbkdf2_sha256.hash(password)
```

### Secure Secret Management
```python
# SECURE - Use environment variables
import os
API_KEY = os.environ.get("API_KEY")

# SECURE - Use secrets manager
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='my-api-key')

# SECURE - Use python-dotenv
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("API_KEY")
```

## Detection Tips
- Look for hashlib.md5(), hashlib.sha1() with "password" nearby
- Search for patterns: API_KEY =, SECRET =, PASSWORD =, TOKEN =
- Check for AWS keys: AKIA..., sk-..., sk_live_...
- Look for connection strings with embedded passwords

## References
- OWASP: https://owasp.org/Top10/A02_2021-Cryptographic_Failures/
- CWE-327: https://cwe.mitre.org/data/definitions/327.html
