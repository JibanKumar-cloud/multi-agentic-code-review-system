# CWE-89: SQL Injection

## Definition
The software constructs all or part of an SQL command using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended SQL command.

## Severity
**CRITICAL** (CVSS 9.8)

## Alternate Names
- SQLi
- SQL Injection Attack

## Vulnerable Code Examples

### Python - Direct Concatenation
```python
# VULNERABLE
username = request.form['username']
query = "SELECT * FROM users WHERE username = '" + username + "'"
cursor.execute(query)

# Attack: username = "admin'--"
# Results in: SELECT * FROM users WHERE username = 'admin'--'
```

### Python - F-String
```python
# VULNERABLE
user_id = request.args.get('id')
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)

# Attack: id = "1 OR 1=1"
# Results in: SELECT * FROM users WHERE id = 1 OR 1=1
```

### Python - Format String
```python
# VULNERABLE
search = request.form['search']
query = "SELECT * FROM products WHERE name LIKE '%{}%'".format(search)
cursor.execute(query)

# Attack: search = "' OR '1'='1"
```

### Python - % Operator
```python
# VULNERABLE
email = request.form['email']
query = "SELECT * FROM users WHERE email = '%s'" % email
cursor.execute(query)
```

## Secure Code Examples

### Parameterized Queries (sqlite3)
```python
# SECURE
username = request.form['username']
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

### Parameterized Queries (psycopg2 - PostgreSQL)
```python
# SECURE
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

### Parameterized Queries (mysql-connector)
```python
# SECURE
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

### SQLAlchemy ORM
```python
# SECURE - ORM automatically parameterizes
user = User.query.filter_by(username=username).first()

# SECURE - SQLAlchemy Core with text()
from sqlalchemy import text
result = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

### Django ORM
```python
# SECURE - Django ORM
user = User.objects.get(username=username)
users = User.objects.filter(name__contains=search_term)
```

## Common Attack Patterns
1. **Authentication Bypass**: `' OR '1'='1`
2. **UNION Attack**: `' UNION SELECT username, password FROM users--`
3. **Stacked Queries**: `'; DROP TABLE users;--`
4. **Blind SQLi**: `' AND (SELECT COUNT(*) FROM users) > 0--`
5. **Time-based Blind**: `' AND SLEEP(5)--`

## Detection Patterns
- f-strings containing SQL keywords: `f"SELECT.*{`
- String concatenation with SQL: `"SELECT" + variable`
- .format() with SQL: `"SELECT.*".format(`
- % formatting with SQL: `"SELECT.*" %`

## References
- https://cwe.mitre.org/data/definitions/89.html
- https://owasp.org/www-community/attacks/SQL_Injection
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
