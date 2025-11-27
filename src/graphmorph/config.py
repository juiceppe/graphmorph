import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Application configuration from environment variables."""

    #LLM Configuration
    anthropic_api_key: str
    model_name: str = "claude-sonnet-4-20250514"
    temperature: float = 0

    #HTTP Settings
    request_timeout: int = 30 #Seconds

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Missing ANTHROPIC_API_KEY environment variable.")
        return cls(
            anthropic_api_key=api_key,
            model_name=os.environ.get("MODEL_NAME", "claude-sonnet-4-20250514"),
            temperature=float(os.environ.get("TEMPERATURE", 0)),
            request_timeout=int(os.environ.get("REQUEST_TIMEOUT", 30)),
        )

_config: Config | None = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config