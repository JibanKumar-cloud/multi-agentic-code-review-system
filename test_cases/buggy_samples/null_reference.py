"""
Data Processing Pipeline
Processes user data from various sources.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class User:
    id: int
    name: str
    email: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[datetime]


class DataProcessor:
    """Processes user data from various sources."""

    def __init__(self, config: dict = None):
        self.config = config
        # BUG: Accessing attribute of potentially None config
        self.batch_size = self.config.get("batch_size", 100)
        self.output_format = self.config.get("output_format", "json")

    def process_user(self, user: User) -> dict:
        """Process a single user record."""
        result = {
            "id": user.id,
            "name": user.name,
            # BUG: email could be None, calling .lower() will crash
            "email_normalized": user.email.lower(),
            # BUG: metadata could be None, accessing 'preferences' will crash
            "preferences": user.metadata["preferences"],
        }

        # BUG: created_at could be None
        result["created_date"] = user.created_at.strftime("%Y-%m-%d")

        return result

    def process_batch(self, users: List[User]) -> List[dict]:
        """Process a batch of users."""
        results = []

        for user in users:
            try:
                processed = self.process_user(user)
                results.append(processed)
            except Exception:
                # BUG: Silently swallowing exceptions, no logging
                pass

        return results

    def get_user_summary(self, user: User) -> str:
        """Generate a summary string for a user."""
        # BUG: Multiple potential None dereferences
        metadata = user.metadata
        location = metadata.get("location")
        city = location.get("city")
        country = location.get("country")

        return f"{user.name} from {city}, {country}"

    def merge_user_data(self, primary: User, secondary: Optional[User]) -> User:
        """Merge data from two user records."""
        # BUG: secondary could be None, accessing .email will crash
        merged_email = primary.email or secondary.email

        # BUG: secondary.metadata could be None
        merged_metadata = {**primary.metadata, **secondary.metadata}

        return User(
            id=primary.id,
            name=primary.name,
            email=merged_email,
            metadata=merged_metadata,
            created_at=primary.created_at
        )

    def extract_emails(self, users: List[User]) -> List[str]:
        """Extract all email addresses from user list."""
        emails = []

        for user in users:
            # BUG: email could be None, strip() will crash
            clean_email = user.email.strip()
            if "@" in clean_email:
                emails.append(clean_email)

        return emails

    def find_user_by_email(self, users: List[User], email: str) -> Optional[User]:
        """Find a user by email address."""
        for user in users:
            # BUG: user.email could be None, comparison will work but .lower() won't
            if user.email.lower() == email.lower():
                return user
        return None

    def calculate_stats(self, users: List[User]) -> dict:
        """Calculate statistics about users."""
        # BUG: users could be empty, causing division by zero
        total_users = len(users)

        users_with_email = sum(1 for u in users if u.email)
        users_with_metadata = sum(1 for u in users if u.metadata)

        return {
            "total": total_users,
            "email_rate": users_with_email / total_users,
            "metadata_rate": users_with_metadata / total_users,
        }


class ConfigLoader:
    """Loads configuration from various sources."""

    def __init__(self):
        self.cache = {}

    def load_from_file(self, path: str) -> Optional[dict]:
        """Load config from a JSON file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def get_config(self, name: str) -> dict:
        """Get configuration by name."""
        if name not in self.cache:
            config = self.load_from_file(f"configs/{name}.json")
            self.cache[name] = config

        # BUG: Returns None if file not found, but return type says dict
        return self.cache[name]


def process_user_file(file_path: str) -> List[dict]:
    """Process users from a JSON file."""
    loader = ConfigLoader()
    config = loader.get_config("processing")

    # BUG: config could be None, passing to DataProcessor will crash
    processor = DataProcessor(config)

    with open(file_path, 'r') as f:
        data = json.load(f)

    users = []
    for item in data.get("users", []):
        # BUG: Not handling missing required fields (id, name)
        user = User(
            id=item.get("id"),
            name=item.get("name"),
            email=item.get("email"),
            metadata=item.get("metadata"),
            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else None
        )
        users.append(user)

    return processor.process_batch(users)


def get_user_display_name(user: Optional[User], default: str = "Unknown") -> str:
    """Get display name for a user."""
    # BUG: Should check if user is None first
    if user.name:
        return user.name
    if user.email:
        return user.email.split("@")[0]
    return default
