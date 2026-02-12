from typing import Optional

from loguru import logger

from miner.config.config import Config
from miner.core.configuration import factory_config

# Singleton — created once on first access, reused for all subsequent requests.
# This eliminates the per-request "Loaded configuration" log spam.
_cached_config: Optional[Config] = None


def get_config() -> Config:
    """Get configuration instance (singleton, created once on first access)."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    try:
        _cached_config = factory_config()
        return _cached_config
    except ValueError as e:
        # Re-raise ValueError (already has formatted message)
        raise
    except Exception as e:
        error_msg = (
            f"\n{'='*70}\n"
            f"CONFIGURATION ERROR: Failed to load miner configuration\n"
            f"{'='*70}\n"
            f"Error: {str(e)}\n"
            f"\nPlease check your environment variables or .env file.\n"
            f"See environments/env.miner.example for valid configuration options.\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e