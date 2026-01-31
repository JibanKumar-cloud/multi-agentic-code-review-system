# CWE-502: Deserialization of Untrusted Data

## Metadata
- ID: CWE-502
- Category: deserialization
- Severity: CRITICAL
- CVSS: 9.8

## Description
The application deserializes untrusted data without sufficiently verifying that the resulting data will be valid. Deserialization of untrusted data can lead to remote code execution.

## Why It's Dangerous
Many serialization formats (pickle, YAML, etc.) can include executable code or object instantiation instructions. An attacker can craft malicious serialized data that, when deserialized, executes arbitrary code.

## Vulnerable Patterns in Python

### pickle.load / pickle.loads
```python
# CRITICAL VULNERABILITY
import pickle

# From file
with open(user_file, 'rb') as f:
    data = pickle.load(f)  # Arbitrary code execution!

# From network/request
data = pickle.loads(request.data)  # RCE!

# From database
cached = redis.get('user_session')
session = pickle.loads(cached)  # If redis is compromised
```

### yaml.load without SafeLoader
```python
# CRITICAL VULNERABILITY
import yaml

# Unsafe - can execute Python code
config = yaml.load(user_input)

# Also unsafe
with open(config_file) as f:
    config = yaml.load(f)
```

### Other Dangerous Deserializers
```python
# marshal - can execute code
import marshal
code = marshal.loads(data)

# shelve - uses pickle internally
import shelve
db = shelve.open(user_controlled_path)

# dill - extended pickle, same risks
import dill
obj = dill.loads(data)

# jsonpickle - can instantiate arbitrary objects
import jsonpickle
obj = jsonpickle.decode(data)

# cloudpickle - same as pickle
import cloudpickle
obj = cloudpickle.loads(data)
```

## Attack Example
```python
# Attacker crafts malicious pickle payload
import pickle
import os

class Exploit:
    def __reduce__(self):
        return (os.system, ('rm -rf /',))

# This payload, when unpickled, executes the command
payload = pickle.dumps(Exploit())

# Victim code
data = pickle.loads(payload)  # Executes: rm -rf /
```

## Secure Alternatives

### Use JSON for Data
```python
# SECURE - JSON only parses data structures
import json

data = json.loads(user_input)
# Can only return: dict, list, str, int, float, bool, None
```

### Use yaml.safe_load
```python
# SECURE - Only allows basic Python types
import yaml

config = yaml.safe_load(user_input)
# Returns: dict, list, str, int, float, bool, None
```

### Use Schema Validation
```python
# SECURE - Explicit schema validation
from pydantic import BaseModel

class UserData(BaseModel):
    name: str
    age: int
    email: str

# Only accepts data matching schema
data = UserData.parse_raw(user_input)
```

### If Pickle is Required
```python
# SECURE - Only from trusted, signed sources
import hmac
import pickle

def secure_unpickle(data: bytes, signature: str, secret: bytes):
    # Verify signature first
    expected = hmac.new(secret, data, 'sha256').hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid signature - data tampered")
    
    # Only unpickle after verification
    return pickle.loads(data)
```

## Detection Signatures
- `pickle.load(` - File deserialization
- `pickle.loads(` - Bytes deserialization  
- `yaml.load(` without `Loader=yaml.SafeLoader`
- `marshal.load` - Code object loading
- `shelve.open(` - Persistent dict (uses pickle)
- `dill.load` or `dill.loads`
- `jsonpickle.decode(`
- `cloudpickle.load`

## Fix Summary

| Vulnerable | Secure Alternative |
|------------|-------------------|
| `pickle.loads(data)` | `json.loads(data)` |
| `yaml.load(data)` | `yaml.safe_load(data)` |
| `marshal.loads(data)` | Don't use for untrusted data |
| `shelve.open(path)` | `json` + file storage |

## References
- https://cwe.mitre.org/data/definitions/502.html
- https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/16-Testing_for_HTTP_Incoming_Requests
- https://docs.python.org/3/library/pickle.html#restricting-globals
