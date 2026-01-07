"""Modular LLM service with support for multiple backends."""

from typing import Dict, Type, Any
import importlib.metadata

from loguru import logger

from miner.core.llms.LLMService import LLMService


def get_backends() -> Dict[str, Type[LLMService]]:
    """Get all available backends from entry points.
    
    Returns:
        Dictionary mapping backend names to backend classes
    """
    backends = {}
    eps = importlib.metadata.entry_points(group="inference.backends")
    
    for ep in eps:
        try:
            backend_class = ep.load()
            backends[ep.name] = backend_class
            logger.info(f"Found backend '{ep.name}': {backend_class.__name__}")
        except ModuleNotFoundError as e:
            logger.warning(
                f"Backend '{ep.name}' not available: module not found ({e.name}). "
                f"Skipping this backend."
            )
        except Exception as e:
            logger.warning(
                f"Backend '{ep.name}' failed to load: {e}. Skipping this backend."
            )
    
    if backends:
        logger.info(f"Loaded {len(backends)} backend(s): {list(backends.keys())}")
    else:
        logger.warning("No backends were successfully loaded")
    
    return backends


BACKENDS: Dict[str, Type[LLMService]] = get_backends()


def get_backend(name: str, config: Any) -> LLMService:
    """Get a backend instance by name.
    
    Args:
        name: Backend name (e.g., "vllm", "ollama", "llamacpp")
        config: Configuration object
        
    Returns:
        LLMService instance
        
    Raises:
        ValueError: If no backends are available
    """
    if name not in BACKENDS:
        if not BACKENDS:
            raise ValueError("No backends available. Check entry points configuration.")
        
        # Select first available backend and log warning
        first_backend = next(iter(BACKENDS.keys()))
        logger.warning(
            f"Backend '{name}' not found. Available backends: {list(BACKENDS.keys())}. "
            f"Using first available backend: '{first_backend}'"
        )
        name = first_backend
    
    return BACKENDS[name](config)


__all__ = ["LLMService", "get_backend", "get_backends", "BACKENDS"]
