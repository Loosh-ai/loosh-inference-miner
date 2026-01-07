from typing import Optional

from fastapi import Depends
from loguru import logger

from miner.config.config import Config
from miner.core.configuration import factory_config

def get_config() -> Config:
    """Get configuration instance."""
    try:
        return factory_config()
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