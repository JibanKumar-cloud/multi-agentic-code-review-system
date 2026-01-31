# Python pickle Module Documentation

## Official Documentation Reference
Source: https://docs.python.org/3/library/pickle.html

## Warning (from Python docs)
> **Warning**: The pickle module is not secure. Only unpickle data you trust.
>
> It is possible to construct malicious pickle data which will execute arbitrary code during unpickling. Never unpickle data that could have come from an untrusted source, or that could have been tampered with.

## Module Purpose
The pickle module implements binary protocols for serializing and de-serializing a Python object structure. "Pickling" converts a Python object into a byte stream, and "unpickling" is the inverse operation.

## Dangerous Functions

### pickle.load() - From File
```python
import pickle

# DANGEROUS - Executes code during unpickling
with open('data.pkl', 'rb') as f:
    obj = pickle.load(f)  # Could execute arbitrary code!
```

### pickle.loads() - From Bytes
```python
import pickle

# DANGEROUS - If data comes from untrusted source
data = receive_from_network()
obj = pickle.loads(data)  # Remote code execution possible!
```

## How Attacks Work
```python
import pickle
import os

class Exploit:
    def __reduce__(self):
        # __reduce__ is called during unpickling
        # Returns a callable and arguments
        return (os.system, ('whoami',))

# Create malicious pickle
payload = pickle.dumps(Exploit())

# When victim unpickles this...
pickle.loads(payload)  # Executes: os.system('whoami')
```

## Safe Alternatives

### Use JSON for Data Exchange
```python
import json

# SAFE - JSON only supports basic data types
data = {"name": "Alice", "age": 30}

# Serialize
json_str = json.dumps(data)

# Deserialize - Cannot execute code
obj = json.loads(json_str)
```

### Use pickle Only for Trusted Data
```python
import pickle
import hmac
import hashlib

SECRET_KEY = b'your-secret-key'

def secure_pickle_dumps(obj):
    """Pickle with HMAC signature."""
    data = pickle.dumps(obj)
    signature = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()
    return data, signature

def secure_pickle_loads(data, signature):
    """Verify signature before unpickling."""
    expected = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid signature - data may be tampered")
    return pickle.loads(data)
```

## Pickle Protocols
```python
import pickle

# Protocol versions
pickle.HIGHEST_PROTOCOL  # Most efficient, Python version specific
pickle.DEFAULT_PROTOCOL  # Default for current Python version

# Specify protocol
data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
```

## Restricting Globals (Partial Mitigation)
```python
import pickle
import io

class RestrictedUnpickler(pickle.Unpickler):
    """Restrict what can be unpickled."""
    
    SAFE_CLASSES = {
        'builtins': {'dict', 'list', 'set', 'tuple', 'str', 'int', 'float'},
    }
    
    def find_class(self, module, name):
        if module in self.SAFE_CLASSES:
            if name in self.SAFE_CLASSES[module]:
                return getattr(__import__(module), name)
        raise pickle.UnpicklingError(f"Forbidden: {module}.{name}")

def restricted_loads(data):
    """Load pickle with restrictions."""
    return RestrictedUnpickler(io.BytesIO(data)).load()
```

## When to Use Pickle
- ✅ Caching Python objects locally
- ✅ Saving ML models (when you control the source)
- ✅ Inter-process communication (within your system)
- ❌ Data from untrusted sources
- ❌ Network communication with external systems
- ❌ User-uploaded files
- ❌ Data stored in shared databases

## Serialization Comparison

| Format | Safe | Speed | Size | Python Types |
|--------|------|-------|------|--------------|
| JSON | ✅ Yes | Fast | Medium | Basic only |
| pickle | ❌ No | Fast | Small | All Python |
| msgpack | ✅ Yes | Fastest | Smallest | Basic + bytes |
| YAML | ⚠️ Depends | Slow | Large | Extended |

## Function Reference

### pickle.dump(obj, file, protocol=None)
Write pickled representation of obj to file.

### pickle.dumps(obj, protocol=None) -> bytes
Return pickled representation as bytes.

### pickle.load(file) -> object
Read and return object from file. **DANGEROUS with untrusted data!**

### pickle.loads(bytes) -> object
Return object from bytes. **DANGEROUS with untrusted data!**

## References
- https://docs.python.org/3/library/pickle.html
- https://docs.python.org/3/library/pickle.html#restricting-globals
- https://nedbatchelder.com/blog/202006/pickles_nine_flaws.html
