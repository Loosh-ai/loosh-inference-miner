"""vLLM implementation."""

from typing import Any

from loguru import logger

try:
    from vllm import LLM, SamplingParams
except ImportError:
    LLM = None
    SamplingParams = None

from miner.core.llms.LLMService import LLMService


class VLLMService(LLMService):
    """LLM service using vLLM."""
    
    def __init__(self, config: Any):
        """Initialize vLLM service."""
        if LLM is None:
            raise ImportError(
                "vllm is not installed. "
                "Install it with: pip install vllm"
            )
        super().__init__(config)
        logger.info("Initialized vLLM service")
    
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """Generate text using vLLM."""
        try:
            # Get or initialize model
            llm = await self._get_model(model)
            
            # Create sampling parameters
            sampling_params = SamplingParams(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens
            )
            
            # Generate response
            outputs = llm.generate([prompt], sampling_params)
            
            # Return generated text
            return outputs[0].outputs[0].text
            
        except Exception as e:
            logger.error(f"Error during text generation with vLLM: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> LLM:
        """Get or initialize a vLLM model."""
        if model_name not in self.models:
            try:
                # Initialize vLLM model
                self.models[model_name] = LLM(
                    model=model_name,
                    tensor_parallel_size=getattr(self.config, 'tensor_parallel_size', 1),
                    gpu_memory_utilization=getattr(
                        self.config, 'gpu_memory_utilization', 0.9
                    ),
                    max_model_len=getattr(self.config, 'max_model_len', 4096),
                )
                logger.info(f"Initialized vLLM model: {model_name}")
            except Exception as e:
                logger.error(f"Error initializing vLLM model {model_name}: {str(e)}")
                raise
        
        return self.models[model_name]
    
    async def health_check(self) -> bool:
        """Check if vLLM service is healthy."""
        try:
            return LLM is not None and SamplingParams is not None
        except Exception:
            return False

