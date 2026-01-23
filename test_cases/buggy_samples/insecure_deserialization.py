"""
Session and Cache Management
Handles session storage and caching with serialization.
"""

import pickle
import base64
import yaml
import json
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import hashlib


class SessionStore:
    """Stores and retrieves user sessions."""

    def __init__(self):
        self.sessions: Dict[str, str] = {}  # session_id -> serialized data

    def create_session(self, user_id: str, data: dict) -> str:
        """Create a new session with user data."""
        session_data = {
            "user_id": user_id,
            "data": data,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }

        # BUG: Using pickle for session serialization - insecure deserialization
        serialized = base64.b64encode(pickle.dumps(session_data)).decode()
        session_id = hashlib.sha256(f"{user_id}_{datetime.now()}".encode()).hexdigest()[:32]

        self.sessions[session_id] = serialized
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data."""
        if session_id not in self.sessions:
            return None

        serialized = self.sessions[session_id]
        # BUG: Deserializing untrusted data with pickle - RCE vulnerability
        session_data = pickle.loads(base64.b64decode(serialized))

        # Check expiration
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.now() > expires_at:
            del self.sessions[session_id]
            return None

        return session_data

    def update_session(self, session_id: str, data: dict) -> bool:
        """Update session data."""
        session = self.get_session(session_id)
        if not session:
            return False

        session["data"].update(data)
        # BUG: Re-serializing with pickle
        serialized = base64.b64encode(pickle.dumps(session)).decode()
        self.sessions[session_id] = serialized
        return True

    def import_session(self, serialized_data: str) -> str:
        """Import a session from serialized data (e.g., from another server)."""
        # BUG: Accepting and deserializing external serialized data
        session_data = pickle.loads(base64.b64decode(serialized_data))

        session_id = hashlib.sha256(
            f"{session_data['user_id']}_{datetime.now()}".encode()
        ).hexdigest()[:32]

        self.sessions[session_id] = serialized_data
        return session_id


class CacheManager:
    """Manages application cache with serialization."""

    def __init__(self):
        self.cache: Dict[str, bytes] = {}

    def set(self, key: str, value: Any, serialize_method: str = "pickle") -> bool:
        """Store a value in cache."""
        try:
            if serialize_method == "pickle":
                # BUG: Using pickle for cache serialization
                serialized = pickle.dumps(value)
            elif serialize_method == "json":
                serialized = json.dumps(value).encode()
            else:
                return False

            self.cache[key] = serialized
            return True
        except Exception:
            return False

    def get(self, key: str, serialize_method: str = "pickle") -> Optional[Any]:
        """Retrieve a value from cache."""
        if key not in self.cache:
            return None

        serialized = self.cache[key]

        try:
            if serialize_method == "pickle":
                # BUG: Deserializing potentially untrusted cached data
                return pickle.loads(serialized)
            elif serialize_method == "json":
                return json.loads(serialized.decode())
        except Exception:
            return None

    def load_from_file(self, filepath: str) -> bool:
        """Load cache from a pickle file."""
        try:
            with open(filepath, 'rb') as f:
                # BUG: Loading pickle from file - could be malicious
                self.cache = pickle.load(f)
            return True
        except Exception:
            return False

    def save_to_file(self, filepath: str) -> bool:
        """Save cache to a pickle file."""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(self.cache, f)
            return True
        except Exception:
            return False


class ConfigLoader:
    """Loads configuration from various file formats."""

    def load_yaml(self, filepath: str) -> dict:
        """Load configuration from YAML file."""
        with open(filepath, 'r') as f:
            # BUG: yaml.load without safe_loader - allows arbitrary code execution
            return yaml.load(f, Loader=yaml.FullLoader)

    def load_yaml_string(self, yaml_string: str) -> dict:
        """Load configuration from YAML string."""
        # BUG: Even worse - loading YAML from potentially untrusted string
        return yaml.load(yaml_string, Loader=yaml.UnsafeLoader)

    def load_from_request(self, request_data: dict) -> dict:
        """Load config from API request (supports multiple formats)."""
        format_type = request_data.get("format", "json")
        content = request_data.get("content", "")

        if format_type == "json":
            return json.loads(content)
        elif format_type == "yaml":
            # BUG: User-controlled YAML parsing
            return yaml.load(content, Loader=yaml.FullLoader)
        elif format_type == "pickle":
            # BUG: User-controlled pickle deserialization - critical RCE
            return pickle.loads(base64.b64decode(content))

        return {}


class ObjectStore:
    """Generic object storage with serialization."""

    def __init__(self, storage_path: str = "/tmp/objects"):
        self.storage_path = storage_path

    def save_object(self, name: str, obj: Any) -> str:
        """Save an object to storage."""
        filepath = f"{self.storage_path}/{name}.pkl"
        with open(filepath, 'wb') as f:
            pickle.dump(obj, f)
        return filepath

    def load_object(self, name: str) -> Any:
        """Load an object from storage."""
        filepath = f"{self.storage_path}/{name}.pkl"
        with open(filepath, 'rb') as f:
            # BUG: Loading pickle from disk without validation
            return pickle.load(f)

    def load_from_url(self, url: str) -> Any:
        """Load a serialized object from URL."""
        import urllib.request

        response = urllib.request.urlopen(url)
        data = response.read()

        # BUG: Deserializing data from untrusted URL - critical RCE
        return pickle.loads(data)


class MessageQueue:
    """Simple message queue with serialization."""

    def __init__(self):
        self.queues: Dict[str, list] = {}

    def create_queue(self, name: str):
        """Create a new queue."""
        self.queues[name] = []

    def publish(self, queue_name: str, message: Any):
        """Publish a message to a queue."""
        if queue_name not in self.queues:
            self.create_queue(queue_name)

        # BUG: Serializing messages with pickle
        serialized = pickle.dumps(message)
        self.queues[queue_name].append(serialized)

    def consume(self, queue_name: str) -> Optional[Any]:
        """Consume a message from a queue."""
        if queue_name not in self.queues or not self.queues[queue_name]:
            return None

        serialized = self.queues[queue_name].pop(0)
        # BUG: Deserializing messages - could be from untrusted source
        return pickle.loads(serialized)

    def import_queue(self, queue_name: str, serialized_messages: list):
        """Import messages from another system."""
        if queue_name not in self.queues:
            self.create_queue(queue_name)

        # BUG: Importing serialized messages from external source
        for msg in serialized_messages:
            self.queues[queue_name].append(base64.b64decode(msg))


# API handlers demonstrating vulnerabilities
def handle_session_import(request_data: dict) -> dict:
    """Handle session import from request."""
    store = SessionStore()

    serialized = request_data.get("session_data", "")

    # BUG: Accepting serialized session data from user
    session_id = store.import_session(serialized)

    return {"status": "success", "session_id": session_id}


def handle_config_update(request_data: dict) -> dict:
    """Handle configuration update from request."""
    loader = ConfigLoader()

    # BUG: Loading config from user-controlled format and content
    config = loader.load_from_request(request_data)

    return {"status": "success", "config": config}


def handle_cache_restore(request_data: dict) -> dict:
    """Handle cache restoration from backup."""
    cache = CacheManager()

    backup_path = request_data.get("backup_path", "")

    # BUG: Loading pickle from user-specified path
    cache.load_from_file(backup_path)

    return {"status": "success", "message": "Cache restored"}
