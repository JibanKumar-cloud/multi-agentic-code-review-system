# OWASP A08:2021 - Software and Data Integrity Failures

## Overview
Insecure deserialization often leads to remote code execution. Even if deserialization flaws do not result in RCE, they can be used for replay attacks, injection attacks, and privilege escalation.

## Category
- **CWE-502**: Deserialization of Untrusted Data
- **CWE-915**: Improperly Controlled Modification of Dynamically-Determined Object Attributes

## Severity
**CRITICAL** - Can lead to remote code execution, complete system compromise.

## Common Patterns in Python

### Pickle (Most Dangerous)
```python
# VULNERABLE - pickle.load from untrusted source
import pickle
with open(user_provided_file, 'rb') as f:
    data = pickle.load(f)  # RCE possible!

# VULNERABLE - pickle.loads from network
data = pickle.loads(request.data)  # RCE possible!
```

### YAML Unsafe Load
```python
# VULNERABLE - yaml.load without safe Loader
import yaml
with open(config_file) as f:
    config = yaml.load(f)  # Can execute arbitrary Python!

# VULNERABLE - yaml.load with user input
config = yaml.load(user_input)
```

### Other Dangerous Deserializers
```python
# VULNERABLE - marshal
import marshal
code = marshal.loads(data)

# VULNERABLE - shelve (uses pickle internally)
import shelve
db = shelve.open(user_file)

# VULNERABLE - dill (extended pickle)
import dill
obj = dill.loads(data)

# VULNERABLE - jsonpickle
import jsonpickle
obj = jsonpickle.decode(data)
```

## Fixes

### Safe Alternatives
```python
# SECURE - Use JSON for data serialization
import json
data = json.loads(user_input)  # Only parses data, no code execution

# SECURE - yaml.safe_load
import yaml
config = yaml.safe_load(user_input)  # Only parses basic types

# SECURE - Use explicit schema validation
from marshmallow import Schema, fields
class UserSchema(Schema):
    name = fields.Str(required=True)
    email = fields.Email(required=True)

schema = UserSchema()
user = schema.load(user_input)
```

### If Pickle is Required
```python
# SECURE - Only load from trusted, signed sources
import hmac
import pickle

def secure_load(data, signature, secret_key):
    expected_sig = hmac.new(secret_key, data, 'sha256').hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid signature")
    return pickle.loads(data)  # Only if signature verified
```

## Detection Tips
- Search for: pickle.load, pickle.loads, marshal.load
- Look for: yaml.load without Loader=yaml.SafeLoader
- Check for: shelve.open, dill.loads, cloudpickle.loads
- Flag any deserialization of user-controlled input

## References
- OWASP: https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/
- CWE-502: https://cwe.mitre.org/data/definitions/502.html
