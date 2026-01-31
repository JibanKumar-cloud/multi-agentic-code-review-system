# PyYAML Module Documentation

## Documentation Reference
Source: https://pyyaml.org/wiki/PyYAMLDocumentation

## Module Purpose
PyYAML is a YAML parser and emitter for Python. YAML is a human-readable data serialization format often used for configuration files.

## Critical Security Warning

> **Warning**: `yaml.load()` can execute arbitrary Python code! Always use `yaml.safe_load()` for untrusted input.

## Dangerous Functions

### yaml.load() Without Loader - DANGEROUS
```python
import yaml

# CRITICAL VULNERABILITY - Can execute arbitrary code!
with open('config.yaml') as f:
    config = yaml.load(f)  # Vulnerable to code execution!

# Attack payload in YAML:
# !!python/object/apply:os.system ['rm -rf /']
```

### yaml.load() with FullLoader - Still Risky
```python
# RISKY - FullLoader can still instantiate some Python objects
config = yaml.load(data, Loader=yaml.FullLoader)
```

### yaml.unsafe_load() - Never Use with Untrusted Data
```python
# DANGEROUS - Explicitly unsafe
config = yaml.unsafe_load(data)  # Full Python object support = full RCE
```

## Safe Functions

### yaml.safe_load() - Recommended
```python
import yaml

# SAFE - Only loads basic YAML types
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Returns only: dict, list, str, int, float, bool, None, datetime
# Cannot execute code or instantiate arbitrary objects
```

### yaml.safe_load_all() - Multiple Documents
```python
import yaml

# SAFE - Load multiple YAML documents
with open('multi.yaml') as f:
    for doc in yaml.safe_load_all(f):
        print(doc)
```

### yaml.SafeLoader - Explicit Loader
```python
import yaml

# SAFE - Explicitly specify SafeLoader
config = yaml.load(data, Loader=yaml.SafeLoader)

# Equivalent to yaml.safe_load()
```

## YAML Attack Examples

### Remote Code Execution
```yaml
# Malicious YAML payload
!!python/object/apply:os.system ['whoami']

# When loaded with yaml.load(), executes: os.system('whoami')
```

### Arbitrary Object Instantiation
```yaml
# Creates arbitrary Python object
!!python/object:module.ClassName
  attribute: value
```

### Subprocess Execution
```yaml
# Executes subprocess
!!python/object/apply:subprocess.check_output
  args: [['cat', '/etc/passwd']]
```

## Safe YAML Usage Patterns

### Loading Configuration Files
```python
import yaml

def load_config(filepath: str) -> dict:
    """Safely load YAML configuration."""
    with open(filepath) as f:
        return yaml.safe_load(f)
```

### Parsing User Input
```python
import yaml

def parse_yaml_input(data: str) -> dict:
    """Safely parse user-provided YAML."""
    try:
        return yaml.safe_load(data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}")
```

### Writing YAML
```python
import yaml

data = {'name': 'Alice', 'age': 30}

# Write to file
with open('output.yaml', 'w') as f:
    yaml.safe_dump(data, f, default_flow_style=False)

# Get string
yaml_str = yaml.safe_dump(data)
```

## Loader Comparison

| Loader | Safe | Python Objects | Use Case |
|--------|------|----------------|----------|
| `SafeLoader` | ✅ Yes | ❌ No | User input, untrusted files |
| `FullLoader` | ⚠️ Partial | ⚠️ Limited | Trusted files (not recommended) |
| `UnsafeLoader` | ❌ No | ✅ Yes | Never use with untrusted data |
| `BaseLoader` | ✅ Yes | ❌ No | Strings only (very limited) |

## Common YAML Data Types
```yaml
# Strings
name: "Alice"
name: Alice
name: 'Alice'

# Numbers
count: 42
price: 19.99

# Booleans
enabled: true
disabled: false

# Null
value: null
value: ~

# Lists
items:
  - apple
  - banana
  - cherry

# Dictionaries
person:
  name: Alice
  age: 30

# Multi-line strings
description: |
  This is a
  multi-line string

# Inline (flow) style
items: [1, 2, 3]
person: {name: Alice, age: 30}
```

## Error Handling
```python
import yaml

try:
    config = yaml.safe_load(user_input)
except yaml.YAMLError as e:
    if hasattr(e, 'problem_mark'):
        mark = e.problem_mark
        print(f"Error at line {mark.line + 1}, column {mark.column + 1}")
    raise ValueError(f"Invalid YAML: {e}")
```

## Custom Types (Safe Way)
```python
import yaml

# Define safe custom constructor
def timestamp_constructor(loader, node):
    value = loader.construct_scalar(node)
    return datetime.fromisoformat(value)

# Register with SafeLoader
yaml.SafeLoader.add_constructor('!timestamp', timestamp_constructor)

# Now can use custom tag safely
data = yaml.safe_load("created: !timestamp 2024-01-15T10:30:00")
```

## Migration Guide

### From Unsafe to Safe
```python
# OLD (Vulnerable)
config = yaml.load(data)

# NEW (Safe)
config = yaml.safe_load(data)
```

```python
# OLD (Vulnerable)
for doc in yaml.load_all(data):
    process(doc)

# NEW (Safe)
for doc in yaml.safe_load_all(data):
    process(doc)
```

## Alternatives to PyYAML

| Library | Safe by Default | Notes |
|---------|-----------------|-------|
| `ruamel.yaml` | ⚠️ No | More features, same risks |
| `strictyaml` | ✅ Yes | Type-safe, no dangerous features |
| `json` | ✅ Yes | Less readable, safer |
| `toml` | ✅ Yes | Good for config files |

## References
- https://pyyaml.org/wiki/PyYAMLDocumentation
- https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
- https://blog.rubygems.org/2013/01/31/data-verification.html (Ruby, but same concept)
