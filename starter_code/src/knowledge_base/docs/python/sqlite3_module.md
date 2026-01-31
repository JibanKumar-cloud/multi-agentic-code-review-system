# Python sqlite3 Module Documentation

## Official Documentation Reference
Source: https://docs.python.org/3/library/sqlite3.html

## Module Purpose
SQLite is a C library that provides a lightweight disk-based database. The sqlite3 module provides an SQL interface compliant with DB-API 2.0.

## SQL Injection Warning

> **Warning**: User input should never be directly concatenated into SQL queries. Always use parameter substitution.

## Dangerous Patterns

### String Concatenation - VULNERABLE
```python
import sqlite3

# DANGEROUS - SQL Injection!
username = request.args.get('username')
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")

# Attack: username = "admin'--"
# Query becomes: SELECT * FROM users WHERE username = 'admin'--'
# This bypasses any password check
```

### String Format - VULNERABLE
```python
# DANGEROUS - Also vulnerable
cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)
cursor.execute("SELECT * FROM users WHERE id = {}".format(user_id))
```

## Safe Patterns - Parameter Substitution

### Positional Parameters (?)
```python
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# SAFE - Use ? placeholder
username = request.args.get('username')
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))

# Multiple parameters
cursor.execute(
    "SELECT * FROM users WHERE username = ? AND status = ?",
    (username, 'active')
)
```

### Named Parameters (:name)
```python
# SAFE - Use :name placeholders
cursor.execute(
    "SELECT * FROM users WHERE username = :user AND role = :role",
    {"user": username, "role": "admin"}
)
```

### executemany() for Bulk Operations
```python
# SAFE - Bulk insert with parameters
users = [
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com'),
]
cursor.executemany(
    "INSERT INTO users (username, email) VALUES (?, ?)",
    users
)
```

## Connection Management

### Using Context Manager (Recommended)
```python
import sqlite3

# SAFE - Auto-commits or rollbacks on exit
with sqlite3.connect('database.db') as conn:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name) VALUES (?)", ('Alice',))
    # Auto-commits if no exception
# Connection closed automatically
```

### Manual Connection
```python
import sqlite3

conn = sqlite3.connect('database.db')
try:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name) VALUES (?)", ('Alice',))
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

## Row Factory for Better Results
```python
import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row  # Access columns by name

cursor = conn.cursor()
cursor.execute("SELECT * FROM users WHERE id = ?", (1,))
row = cursor.fetchone()

# Access by name
print(row['username'])
print(row['email'])

# Still works by index
print(row[0])
```

## Common Functions

### Connection Functions
```python
conn = sqlite3.connect('database.db')  # Open database
conn = sqlite3.connect(':memory:')      # In-memory database
conn.close()                            # Close connection
conn.commit()                           # Commit transaction
conn.rollback()                         # Rollback transaction
```

### Cursor Functions
```python
cursor = conn.cursor()
cursor.execute(sql, params)         # Execute single query
cursor.executemany(sql, params_seq) # Execute with multiple param sets
cursor.fetchone()                   # Fetch one row
cursor.fetchall()                   # Fetch all rows
cursor.fetchmany(size)              # Fetch 'size' rows
cursor.lastrowid                    # Last inserted row ID
cursor.rowcount                     # Rows affected by last operation
```

## Table Operations
```python
# Create table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Insert (with parameter)
cursor.execute(
    "INSERT INTO users (username, email) VALUES (?, ?)",
    (username, email)
)

# Select (with parameter)
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
user = cursor.fetchone()

# Update (with parameter)
cursor.execute(
    "UPDATE users SET email = ? WHERE id = ?",
    (new_email, user_id)
)

# Delete (with parameter)
cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
```

## LIKE Queries - Safe Pattern
```python
# SAFE - Escape % and _ in user input for LIKE
search_term = user_input.replace('%', '\\%').replace('_', '\\_')
cursor.execute(
    "SELECT * FROM users WHERE username LIKE ? ESCAPE '\\'",
    (f'%{search_term}%',)
)
```

## Common Mistakes

### Mistake 1: Forgetting the Tuple for Single Parameter
```python
# WRONG - String is iterated character by character
cursor.execute("SELECT * FROM users WHERE id = ?", user_id)

# CORRECT - Use tuple with trailing comma
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### Mistake 2: Using IN with f-string
```python
# WRONG - Vulnerable to injection
ids = [1, 2, 3]
cursor.execute(f"SELECT * FROM users WHERE id IN ({','.join(map(str, ids))})")

# CORRECT - Generate placeholders dynamically
placeholders = ','.join('?' * len(ids))
cursor.execute(f"SELECT * FROM users WHERE id IN ({placeholders})", ids)
```

### Mistake 3: Not Committing
```python
# WRONG - Changes not saved
cursor.execute("INSERT INTO users (name) VALUES (?)", ('Alice',))
conn.close()  # Changes lost!

# CORRECT - Commit before closing
cursor.execute("INSERT INTO users (name) VALUES (?)", ('Alice',))
conn.commit()
conn.close()
```

## References
- https://docs.python.org/3/library/sqlite3.html
- https://www.sqlite.org/lang.html
- https://bobby-tables.com/python (SQL injection examples)
