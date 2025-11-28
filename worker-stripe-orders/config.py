from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import os


def find_env_file() -> str:
    """Find .env file - check local dir, then project root."""
    local_env = Path(".env")
    root_env = Path("../.env")
    
    if local_env.exists():
        return str(local_env)
    elif root_env.exists():
        return str(root_env)
    return ".env"  # default


class Config(BaseSettings):
    """Configuration for the Stripe orders worker."""
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    
    # Polling
    POLL_INTERVAL_SECONDS: int = 300  # 5 minutes
    
    # Storage
    ORDERS_DIR: str = "Orders"
    STATE_DIR: str = "state"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = find_env_file()
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_config() -> Config:
    """Get configuration instance."""
    return Config()

