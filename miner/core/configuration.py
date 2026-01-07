"""
Miner configuration factory using Pydantic 2 with environment variable support.
"""

from pathlib import Path
from loguru import logger

from miner.config.config import MinerConfig


def factory_config() -> MinerConfig:
    """Create configuration from environment variables using Pydantic 2."""
    try:
        # Create configuration using Pydantic 2 BaseSettings
        # This automatically loads from environment variables and .env file
        config = MinerConfig()
        
        logger.info("Loaded configuration:")
        logger.info(f"Network: {config.subtensor_network}")
        logger.info(f"Subnet: {config.netuid}")
        logger.info(f"Wallet: {config.wallet_name}")
        logger.info(f"Hotkey: {config.hotkey_name}")
        logger.info(f"API: {config.api_host}:{config.api_port}")
        logger.info(f"Model: {config.default_model}")
        logger.info(f"GPU Memory: {config.gpu_memory_utilization}")
        logger.info(f"Max Model Length: {config.max_model_len}")
        
        return config
    except Exception as e:
        error_msg = (
            f"\n{'='*70}\n"
            f"CONFIGURATION ERROR: Failed to load miner configuration\n"
            f"{'='*70}\n"
            f"Error: {str(e)}\n"
            f"\nThis is usually caused by:\n"
            f"  - Invalid environment variable values\n"
            f"  - Missing required configuration\n"
            f"  - Type validation errors (e.g., invalid number format)\n"
            f"\nPlease check your environment variables or .env file.\n"
            f"See environments/env.miner.example for valid configuration options.\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e 