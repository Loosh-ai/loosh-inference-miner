"""Ollama implementation."""

from typing import Any
import asyncio
import ollama

from loguru import logger

from miner.core.llms.LLMService import LLMService


class OllamaService(LLMService):
    """LLM service using local Ollama package."""
    
    def __init__(self, config: Any):
        """Initialize Ollama service."""
        super().__init__(config)
        # Get Ollama host from config, default to localhost
        self.host = getattr(config, 'ollama_host', 'localhost')
        logger.info(f"Initialized Ollama service with host: {self.host}")
    
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """Generate text using Ollama."""
        try:
            # Run ollama.generate in executor since it's synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.generate(
                    model=model,
                    prompt=prompt,
                    options={
                        "num_predict": max_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                    }
                )
            )
            return response.get("response", "")
                
        except Exception as e:
            logger.error(f"Error during text generation with Ollama: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> str:
        """Verify model is available in Ollama.
        
        This doesn't actually load the model, but checks if it's available.
        """
        try:
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                lambda: ollama.list()
            )
            model_names = [m.get("name", "") for m in models.get("models", [])]
            
            if model_name not in model_names:
                logger.warning(
                    f"Model {model_name} not found in Ollama. "
                    f"Available models: {model_names}"
                )
            
            return model_name
                
        except Exception as e:
            logger.error(f"Error checking Ollama model {model_name}: {str(e)}")
            raise
    
    async def health_check(self) -> bool:
        """Check if Ollama service is healthy."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: ollama.list())
            return True
        except Exception:
            return False

