"""
Miner configuration using Pydantic 2 with environment variable support.
"""

from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# CONFIG - MinerConfig [

class MinerConfig(BaseSettings):
    """Configuration for the miner using Pydantic 2 BaseSettings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Network configuration
    #netuid: int = Field(default=21, description="Subnet UID")
    #subtensor_network: str = Field(default="finney", description="Network to connect to")
    #subtensor_address: str = Field(
    #    default="wss://entrypoint-finney.opentensor.ai:443",
    #    description="Network entrypoint"
    #)
    
    netuid: int = Field(default=1, description="Subnet UID")
    subtensor_network: str = Field(default="local", description="Network to connect to")
    subtensor_address: str = Field(
        default="ws://127.0.0.1:9945",
        description="Network entrypoint"
    )

    # Wallet configuration
    wallet_name: str = Field(default="miner", description="Wallet name")
    hotkey_name: str = Field(default="miner", description="Hotkey name")
    
    # API configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    
    # LLM configuration
    llm_backend: str = Field(
        default="llamacpp",
        description="LLM backend to use: 'vllm', 'ollama', or 'llamacpp'"
    )
    default_model: str = Field(
        default="mistralai/Mistral-7B-v0.1",
        description="Default model to use"
    )
    default_max_tokens: int = Field(default=512, description="Default max tokens")
    default_temperature: float = Field(default=0.7, description="Default temperature")
    default_top_p: float = Field(default=0.95, description="Default top-p value")
    
    # Backend-specific configuration
    model_path: Optional[str] = Field(
        default=None,
        description="Path to model file (for llama.cpp)"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    ollama_timeout: float = Field(
        default=300.0,
        description="Ollama API timeout in seconds"
    )
    vllm_api_base: str = Field(
        default="http://localhost:8000/v1",
        description="vLLM API base URL (OpenAI-compatible endpoint)"
    )
    
    # GPU configuration
    tensor_parallel_size: int = Field(default=1, description="Number of GPU layers to use")
    gpu_memory_utilization: float = Field(
        default=0.9, 
        description="GPU memory utilization",
        ge=0.0,
        le=1.0
    )
    max_model_len: int = Field(default=4096, description="Maximum context length")
    
    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Test mode configuration
    test_mode: bool = Field(
        default=False,
        description="Enable test mode - returns success message without running inference"
    )
    
    # Fiber MLTS Configuration
    fiber_key_ttl_seconds: int = Field(
        default=3600,
        description="Time-to-live for Fiber symmetric keys in seconds (default: 1 hour)"
    )
    fiber_handshake_timeout_seconds: int = Field(
        default=30,
        description="Timeout for Fiber handshake operations in seconds"
    )
    fiber_enable_key_rotation: bool = Field(
        default=True,
        description="Enable automatic key rotation for Fiber symmetric keys"
    )
    
    # Concurrency configuration
    max_concurrent_requests: int = Field(
        default=10,
        description="Maximum number of concurrent inference requests to process"
    )


# Legacy alias for backward compatibility
Config = MinerConfig

# CONFIG - MinerConfig ]
