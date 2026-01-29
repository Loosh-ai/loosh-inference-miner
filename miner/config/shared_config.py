"""
Shared configuration models using Pydantic 2 with environment variable support.
Miner-specific version - only includes miner-relevant configuration.
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import Optional, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""
    
    model_config = SettingsConfigDict(
        env_file=("/workspace/.env", ".env"),  # Check RunPod location first, then local
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class NetworkConfig(BaseConfig):
    """Network configuration settings."""
    
    netuid: int = Field(default=1, description="Subnet UID")
    subtensor_network: str = Field(default="local", description="Network to connect to")
    subtensor_address: str = Field(
        default="ws://127.0.0.1:9945",
        description="Network entrypoint"
    )


class WalletConfig(BaseConfig):
    """Wallet configuration settings."""
    
    wallet_name: str = Field(default="miner", description="Wallet name")
    hotkey_name: str = Field(default="miner", description="Hotkey name")


class APIConfig(BaseConfig):
    """API configuration settings."""
    
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")


class LLMConfig(BaseConfig):
    """LLM configuration settings."""
    
    default_model: str = Field(
        default="mistralai/Mistral-7B-v0.1",
        description="Default model to use"
    )
    default_max_tokens: int = Field(default=512, description="Default max tokens")
    default_temperature: float = Field(default=0.7, description="Default temperature")
    default_top_p: float = Field(default=0.95, description="Default top-p value")


class GPUConfig(BaseConfig):
    """GPU configuration settings."""
    
    tensor_parallel_size: int = Field(default=1, description="Number of GPU layers to use")
    gpu_memory_utilization: float = Field(
        default=0.9, 
        description="GPU memory utilization",
        ge=0.0,
        le=1.0
    )
    max_model_len: int = Field(default=4096, description="Maximum context length")


class LoggingConfig(BaseConfig):
    """Logging configuration settings."""
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", 
        description="Logging level"
    )
    log_file: Optional[str] = Field(default=None, description="Log file path")


class MinerConfig(BaseConfig):
    """Complete miner configuration."""
    
    # Sub-configurations
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    wallet: WalletConfig = Field(default_factory=WalletConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    gpu: GPUConfig = Field(default_factory=GPUConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Axon port for bittensor communication
    axon_port: int = Field(default=8089, description="Bittensor axon port for miner communication")

    # Network configuration (direct fields for compatibility)
    netuid: int = Field(default=21, description="Subnet UID")
    subtensor_network: str = Field(default="finney", description="Network to connect to")
    subtensor_address: str = Field(
        default="wss://entrypoint-finney.opentensor.ai:443",
        description="Network entrypoint"
    )
    wallet_name: str = Field(default="miner", description="Wallet name")
    hotkey_name: str = Field(default="miner", description="Hotkey name")
    
    # Test mode configuration
    test_mode: bool = Field(
        default=False,
        description="Enable test mode - returns success message without running inference"
    )


def get_miner_config() -> MinerConfig:
    """Get miner configuration from environment variables."""
    return MinerConfig()


