"""llama.cpp implementation."""

from typing import Any

from loguru import logger

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

from miner.core.llms.LLMService import LLMService


class LlamaCppService(LLMService):
    """LLM service using llama-cpp-python."""
    
    def __init__(self, config: Any):
        """Initialize llama.cpp service."""
        if Llama is None:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Install it with: pip install llama-cpp-python"
            )
        super().__init__(config)
        logger.info("Initialized llama.cpp service")
    
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """Generate text using llama-cpp-python."""
        try:
            # Get or initialize model
            llm = await self._get_model(model)
            
            # Generate response using llama-cpp-python
            output = llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                echo=False
            )
            
            # Return generated text
            return output['choices'][0]['text']
            
        except Exception as e:
            logger.error(f"Error during text generation with llama.cpp: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> Llama:
        """Get or initialize a model."""
        if model_name not in self.models:
            try:
                # Use model_path from config if set, otherwise use model_name as path
                model_path = getattr(self.config, 'model_path', None)
                if not model_path:
                    # If no model_path in config, use model_name directly
                    model_path = model_name
                
                # Initialize model using llama-cpp-python
                self.models[model_name] = Llama(
                    model_path=model_path,
                    n_gpu_layers=getattr(self.config, 'tensor_parallel_size', 0),
                    n_ctx=getattr(self.config, 'max_model_len', 4096),
                    verbose=False
                )
                logger.info(f"Initialized llama.cpp model: {model_name} at {model_path}")
            except Exception as e:
                logger.error(f"Error initializing llama.cpp model {model_name}: {str(e)}")
                raise
        
        return self.models[model_name]
    
    async def health_check(self) -> bool:
        """Check if llama.cpp service is healthy."""
        try:
            return Llama is not None
        except Exception:
            return False

