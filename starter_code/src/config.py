"""
Configuration module for the Multi-Agent Code Review System.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for individual agents."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 0.1
    thinking_budget: int = 5000
    timeout: float = 120.0


@dataclass
class Config:
    """Global configuration for the system."""
    
    # API Configuration
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    # Model Configuration
    default_model: str = "claude-sonnet-4-20250514"
    
    # Agent Configurations
    coordinator_config: AgentConfig = field(default_factory=lambda: AgentConfig(
        max_tokens=8192,
        temperature=0.1
    ))
    
    security_config: AgentConfig = field(default_factory=lambda: AgentConfig(
        max_tokens=8192,
        temperature=0.0,
        thinking_budget=6000
    ))
    
    bug_config: AgentConfig = field(default_factory=lambda: AgentConfig(
        max_tokens=8192,
        temperature=0.0,
        thinking_budget=6000
    ))
    
    quality_config: AgentConfig = field(default_factory=lambda: AgentConfig(
        max_tokens=8192,
        temperature=0.1,
        thinking_budget=4000
    ))
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    
    # File Configuration
    supported_extensions: List[str] = field(default_factory=lambda: [".py"])
    max_file_size: int = 100_000  # 100KB
    
    # Analysis Configuration
    parallel_agents: bool = True
    max_concurrent_agents: int = 3
    
    def validate(self) -> None:
        """Validate the configuration."""
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )


# Global config instance
config = Config()
