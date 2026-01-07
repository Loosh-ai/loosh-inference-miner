"""Base LLM service class."""

from typing import Any, Dict


class LLMService:
    """Base LLM service class."""
    
    def __init__(self, config: Any):
        """Initialize LLM service with configuration.
        
        Args:
            config: Configuration object with backend-specific settings
        """
        self.config = config
        self.models: Dict[str, Any] = {}
    
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """Generate text using the specified model.
        
        Args:
            prompt: Input prompt text
            model: Model name/identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            
        Returns:
            Generated text string
        """
        raise NotImplementedError("Subclasses must implement generate()")
    
    async def _get_model(self, model_name: str) -> Any:
        """Get or initialize a model.
        
        Args:
            model_name: Name/identifier of the model
            
        Returns:
            Model object (backend-specific)
        """
        raise NotImplementedError("Subclasses must implement _get_model()")
    
    async def health_check(self) -> bool:
        """Check if the service is healthy and ready.
        
        Returns:
            True if service is healthy, False otherwise
        """
        return True

