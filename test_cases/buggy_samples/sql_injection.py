"""
User Management Module
Handles user authentication and profile management.
"""

import sqlite3
import hashlib
from typing import Optional, Dict, Any


class UserManager:
    """Manages user accounts and authentication."""

    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        cursor = self.connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1
            )
        """)
        self.connection.commit()

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username and password.
        Returns user data if successful, None otherwise.
        """
        password_hash = hashlib.md5(password.encode()).hexdigest()

        cursor = self.connection.cursor()
        # BUG: SQL Injection vulnerability - user input directly in query
        query = f"SELECT id, username, email, role FROM users WHERE username = '{username}' AND password_hash = '{password_hash}'"
        cursor.execute(query)

        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "role": row[3]
            }
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve user by ID."""
        cursor = self.connection.cursor()
        # BUG: SQL Injection - even though user_id should be int, no validation
        query = f"SELECT id, username, email, role FROM users WHERE id = {user_id}"
        cursor.execute(query)

        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "role": row[3]
            }
        return None

    def search_users(self, search_term: str) -> list:
        """Search users by username or email."""
        cursor = self.connection.cursor()
        # BUG: SQL Injection with LIKE clause
        query = f"SELECT id, username, email FROM users WHERE username LIKE '%{search_term}%' OR email LIKE '%{search_term}%'"
        cursor.execute(query)

        return [{"id": row[0], "username": row[1], "email": row[2]} for row in cursor.fetchall()]

    def update_user_role(self, user_id: int, new_role: str) -> bool:
        """Update a user's role (admin only operation)."""
        cursor = self.connection.cursor()
        # BUG: SQL Injection in UPDATE statement
        query = f"UPDATE users SET role = '{new_role}' WHERE id = {user_id}"
        cursor.execute(query)
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """Delete a user by username."""
        cursor = self.connection.cursor()
        # BUG: SQL Injection in DELETE statement
        query = f"DELETE FROM users WHERE username = '{username}'"
        cursor.execute(query)
        self.connection.commit()
        return cursor.rowcount > 0

    def create_user(self, username: str, password: str, email: str = None) -> int:
        """Create a new user account."""
        # BUG: Using MD5 for password hashing (weak/broken)
        password_hash = hashlib.md5(password.encode()).hexdigest()

        cursor = self.connection.cursor()
        # This one uses parameterized query (correct)
        cursor.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email)
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_all_users(self) -> list:
        """Get all users (safe query, no user input)."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT id, username, email, role FROM users")
        return [{"id": row[0], "username": row[1], "email": row[2], "role": row[3]} for row in cursor.fetchall()]


# API endpoint handlers
def handle_login(request_data: dict) -> dict:
    """Handle login API request."""
    manager = UserManager()

    username = request_data.get("username", "")
    password = request_data.get("password", "")

    user = manager.authenticate(username, password)

    if user:
        return {"status": "success", "user": user}
    return {"status": "error", "message": "Invalid credentials"}


def handle_search(request_data: dict) -> dict:
    """Handle user search API request."""
    manager = UserManager()

    search_term = request_data.get("q", "")
    results = manager.search_users(search_term)

    return {"status": "success", "results": results}


def handle_delete_user(request_data: dict) -> dict:
    """Handle user deletion API request."""
    manager = UserManager()

    username = request_data.get("username", "")
    success = manager.delete_user(username)

    if success:
        return {"status": "success"}
    return {"status": "error", "message": "User not found"}
