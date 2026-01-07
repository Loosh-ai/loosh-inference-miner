"""LLM service module - exports the modular LLMService."""

from miner.core.llms import LLMService, get_backend

__all__ = ["LLMService", "get_backend"]
