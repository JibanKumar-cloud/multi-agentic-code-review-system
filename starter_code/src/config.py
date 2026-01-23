"""
Configuration management for the multi-agent system.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for an individual agent."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    thinking_budget: int = 10000  # For extended thinking


@dataclass
class SystemConfig:
    """System-wide configuration."""
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Agent configurations
    coordinator_config: AgentConfig = field(default_factory=AgentConfig)
    security_agent_config: AgentConfig = field(default_factory=AgentConfig)
    bug_agent_config: AgentConfig = field(default_factory=AgentConfig)

    # Streaming settings
    stream_buffer_size: int = 100
    event_queue_maxsize: int = 1000

    # Analysis settings
    max_file_size_bytes: int = 100_000  # 100KB
    supported_extensions: tuple = (".py",)

    def validate(self) -> bool:
        """Validate the configuration."""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return True


# Global configuration instance
config = SystemConfig()
