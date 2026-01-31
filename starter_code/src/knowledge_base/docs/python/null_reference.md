# Python NoneType Errors and Null Reference Bugs

## Overview
NoneType errors occur when code attempts to access attributes or call methods on a `None` value. These are among the most common runtime errors in Python.

## Severity
**MEDIUM to HIGH** - Can cause application crashes and denial of service.

## Common Vulnerable Patterns

### Accessing Attributes Without Checking
```python
# VULNERABLE - user could be None
def get_email(user):
    return user.email.lower()  # AttributeError if user is None

# VULNERABLE - Chained access
def get_city(user):
    return user.profile.address.city  # Multiple None risks
```

### Dictionary Access Without .get()
```python
# VULNERABLE - KeyError if key missing
def get_setting(config, key):
    return config[key]  # Raises KeyError if key not in dict

# VULNERABLE - Chained dictionary access
value = data['user']['preferences']['theme']  # Multiple KeyError risks
```

### Method Calls on Potentially None
```python
# VULNERABLE
def normalize_email(email):
    return email.strip().lower()  # If email is None, crashes

# VULNERABLE - from database
def process_user(user_id):
    user = db.get_user(user_id)  # Might return None
    return user.name  # AttributeError if user not found
```

### Function Return Values
```python
# VULNERABLE - re.search returns None if no match
import re
match = re.search(r'\d+', text)
number = match.group()  # AttributeError if no match

# VULNERABLE - list.pop on empty list
def get_last(items):
    return items.pop()  # IndexError if empty
```

## Secure Patterns

### Explicit None Checks
```python
# SECURE - Check before access
def get_email(user):
    if user is None:
        return None
    if user.email is None:
        return None
    return user.email.lower()
```

### Using getattr() with Default
```python
# SECURE - getattr with default
def get_email(user):
    email = getattr(user, 'email', None)
    return email.lower() if email else None

# SECURE - Nested getattr
def get_city(user):
    profile = getattr(user, 'profile', None)
    address = getattr(profile, 'address', None) if profile else None
    return getattr(address, 'city', None) if address else None
```

### Using dict.get()
```python
# SECURE - .get() with default
def get_setting(config, key):
    return config.get(key)  # Returns None if missing

# SECURE - .get() with explicit default
def get_setting(config, key, default=''):
    return config.get(key, default)

# SECURE - Nested dict access
value = data.get('user', {}).get('preferences', {}).get('theme', 'default')
```

### Optional Chaining Pattern
```python
# SECURE - Helper function for safe attribute access
def safe_get(obj, *attrs, default=None):
    """Safely traverse nested attributes."""
    for attr in attrs:
        if obj is None:
            return default
        obj = getattr(obj, attr, None)
    return obj if obj is not None else default

# Usage
city = safe_get(user, 'profile', 'address', 'city', default='Unknown')
```

### Guard Clauses
```python
# SECURE - Early return pattern
def process_user(user_id):
    user = db.get_user(user_id)
    if user is None:
        return None  # or raise ValueError("User not found")
    return user.name
```

### Walrus Operator (Python 3.8+)
```python
# SECURE - Assign and check in one line
import re

if (match := re.search(r'\d+', text)):
    number = match.group()
else:
    number = None
```

### Type Hints with Optional
```python
from typing import Optional

# SECURE - Type hints document expected None
def get_user(user_id: int) -> Optional[User]:
    """Returns User or None if not found."""
    return db.query(User).filter_by(id=user_id).first()

def process_user(user: Optional[User]) -> str:
    if user is None:
        return "Unknown"
    return user.name
```

## Detection Patterns
- Method calls like `.lower()`, `.upper()`, `.strip()` without None check
- Chained attribute access: `a.b.c`
- Dictionary access with `[]` instead of `.get()`
- Return values from database queries, regex, find operations used directly

## Fix Summary

| Vulnerable | Secure |
|------------|--------|
| `user.email` | `user.email if user else None` |
| `config[key]` | `config.get(key)` |
| `obj.attr.sub` | `getattr(getattr(obj, 'attr', None), 'sub', None)` |
| `match.group()` | `match.group() if match else None` |

## References
- https://docs.python.org/3/library/typing.html#typing.Optional
- https://peps.python.org/pep-0505/ (PEP for None-aware operators - deferred)
