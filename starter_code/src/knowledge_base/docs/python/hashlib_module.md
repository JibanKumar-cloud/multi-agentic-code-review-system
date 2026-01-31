# Python hashlib Module Documentation

## Official Documentation Reference
Source: https://docs.python.org/3/library/hashlib.html

## Module Purpose
This module implements a common interface to many different secure hash and message digest algorithms. Included are the FIPS secure hash algorithms SHA1, SHA224, SHA256, SHA384, and SHA512, as well as RSA's MD5 algorithm.

## Security Warnings

### MD5 is Broken
> **Warning**: MD5 is not collision resistant and should not be used for security purposes.

```python
import hashlib

# INSECURE - MD5 is cryptographically broken
password_hash = hashlib.md5(password.encode()).hexdigest()  # DON'T DO THIS!
```

### SHA1 is Weak
> **Warning**: SHA-1 has known weaknesses and should not be used for security-sensitive applications.

```python
# INSECURE - SHA1 has collision attacks
password_hash = hashlib.sha1(password.encode()).hexdigest()  # DON'T DO THIS!
```

## Available Algorithms
```python
import hashlib

# Guaranteed available on all platforms
hashlib.algorithms_guaranteed
# {'blake2b', 'blake2s', 'md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'shake_128', 'shake_256'}

# Available on this platform
hashlib.algorithms_available  # May include more
```

## Basic Usage

### Creating a Hash
```python
import hashlib

# Method 1: Constructor
h = hashlib.sha256()
h.update(b"Hello ")
h.update(b"World")
digest = h.hexdigest()

# Method 2: One-liner
digest = hashlib.sha256(b"Hello World").hexdigest()
```

### Hash Object Methods
```python
h = hashlib.sha256()

h.update(data)      # Add data to hash (can call multiple times)
h.digest()          # Return binary digest (bytes)
h.hexdigest()       # Return hex string digest
h.copy()            # Return copy of hash object
h.digest_size       # Size of digest in bytes
h.block_size        # Internal block size in bytes
h.name              # Name of algorithm
```

## Secure Password Hashing

### DON'T Use hashlib for Passwords!
```python
# WRONG - No salt, fast to brute force
password_hash = hashlib.sha256(password.encode()).hexdigest()

# WRONG - Even with salt, too fast
password_hash = hashlib.sha256((salt + password).encode()).hexdigest()
```

### Use Purpose-Built Functions
```python
# CORRECT - Use hashlib.scrypt (Python 3.6+)
import hashlib
import os

def hash_password(password: str) -> bytes:
    salt = os.urandom(16)
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14,  # CPU/memory cost
        r=8,      # Block size
        p=1,      # Parallelization
        dklen=32  # Output length
    )
    return salt + key

def verify_password(password: str, stored: bytes) -> bool:
    salt = stored[:16]
    stored_key = stored[16:]
    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=2**14, r=8, p=1, dklen=32
    )
    return key == stored_key
```

### Or Use bcrypt/argon2
```python
# BEST - Use bcrypt
import bcrypt

hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
is_valid = bcrypt.checkpw(password.encode(), hashed)

# BEST - Use argon2
from argon2 import PasswordHasher
ph = PasswordHasher()
hash = ph.hash(password)
is_valid = ph.verify(hash, password)
```

## File Hashing
```python
import hashlib

def hash_file(filepath: str, algorithm: str = 'sha256') -> str:
    """Calculate hash of a file."""
    h = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as f:
        # Read in chunks to handle large files
        while chunk := f.read(8192):
            h.update(chunk)
    
    return h.hexdigest()

# Usage
file_hash = hash_file('document.pdf')
```

## HMAC for Message Authentication
```python
import hmac
import hashlib

# Create HMAC
key = b'secret-key'
message = b'important message'

h = hmac.new(key, message, hashlib.sha256)
signature = h.hexdigest()

# Verify HMAC (use compare_digest to prevent timing attacks!)
def verify_hmac(key, message, signature):
    expected = hmac.new(key, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Algorithm Recommendations

| Use Case | Recommended | Avoid |
|----------|-------------|-------|
| Password hashing | scrypt, bcrypt, argon2 | MD5, SHA-1, SHA-256 alone |
| File integrity | SHA-256, SHA-3 | MD5, SHA-1 |
| Message authentication | HMAC-SHA256 | Plain hash |
| Digital signatures | SHA-256, SHA-3 | MD5, SHA-1 |
| Checksums (non-security) | MD5 is fine | N/A |

## New in Python 3.6+: BLAKE2
```python
import hashlib

# BLAKE2 - Fast and secure
h = hashlib.blake2b(b"data", digest_size=32)  # 256-bit
digest = h.hexdigest()

# BLAKE2 with key (keyed hashing, like HMAC)
h = hashlib.blake2b(b"data", key=b"secret", digest_size=32)
```

## References
- https://docs.python.org/3/library/hashlib.html
- https://docs.python.org/3/library/hmac.html
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
