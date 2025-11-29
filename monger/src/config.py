"""
Monger service configuration.
"""
import json
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service settings from environment variables."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 3002
    
    # LLM Sidecar - Monger talks to this via HTTP
    # The sidecar handles the actual LLM (OpenAI, Ollama, etc.)
    llm_service_url: str = "http://llm:11435"
    llm_service_timeout: float = 120.0  # LLM calls can be slow
    
    # Character config path
    character_config_path: str = "/app/config/monger.json"
    
    # Logging
    log_level: str = "info"
    log_path: str = ""  # e.g. /app/logs/monger.log
    
    # Version
    version: str = "1.0.0"
    
    # Service URLs for diagnostics
    api_service_url: str = "http://api:3001"
    web_service_url: str = "http://web:80"
    
    # Log paths for diagnostics (inside container)
    logs_dir: str = "/app/logs"
    
    class Config:
        env_prefix = ""
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def load_character_config() -> dict:
    """Load the monger character configuration from JSON file."""
    settings = get_settings()
    config_path = Path(settings.character_config_path)
    
    # Also check relative paths for local dev
    if not config_path.exists():
        # Try relative to this file
        alt_path = Path(__file__).parent.parent / "config" / "monger.json"
        if alt_path.exists():
            config_path = alt_path
        else:
            raise FileNotFoundError(
                f"Character config not found at {settings.character_config_path} "
                f"or {alt_path}"
            )
    
    with open(config_path) as f:
        return json.load(f)
