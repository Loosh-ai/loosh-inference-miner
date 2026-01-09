"""Base LLM service class."""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from LLM generation with support for tool calls."""
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    
    def __str__(self) -> str:
        """Return content as string for backward compatibility."""
        return self.content


class LLMService:
    """Base LLM service class with OpenAI-compatible interface."""
    
    def __init__(self, config: Any):
        """Initialize LLM service with configuration.
        
        Args:
            config: Configuration object with backend-specific settings
        """
        self.config = config
        self.models: Dict[str, Any] = {}
    
    async def generate(
        self,
        prompt: Optional[str] = None,
        model: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        messages: Optional[List[Dict[str, str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Union[str, LLMResponse]:
        """Generate text using the specified model.
        
        Supports both legacy prompt-based and OpenAI-compatible message-based interfaces.
        
        Args:
            prompt: Input prompt text (legacy, for backward compatibility)
            model: Model name/identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            messages: List of message dicts in OpenAI format [{"role": "user", "content": "..."}]
            tools: List of tool definitions for function calling
            tool_choice: Tool choice parameter ("auto", "none", or specific tool dict)
            
        Returns:
            Generated text string (legacy) or LLMResponse with content and optional tool_calls
            
        Note:
            If both prompt and messages are provided, messages takes precedence.
            If neither is provided, raises ValueError.
        """
        # Convert prompt to messages format if needed (backward compatibility)
        if messages is None:
            if prompt is None:
                raise ValueError("Either 'prompt' or 'messages' must be provided")
            messages = [{"role": "user", "content": prompt}]
        
        # Call the new chat completion method
        response = await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice
        )
        
        # Return string for backward compatibility if tools were not provided
        # If tools were provided, always return LLMResponse (even if no tool_calls)
        if tools is None:
            return response.content
        return response
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    ) -> LLMResponse:
        """Generate chat completion using OpenAI-compatible message format.
        
        Args:
            messages: List of message dicts in OpenAI format
            model: Model name/identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            tools: List of tool definitions for function calling
            tool_choice: Tool choice parameter ("auto", "none", or specific tool dict)
            
        Returns:
            LLMResponse with content and optional tool_calls
        """
        raise NotImplementedError("Subclasses must implement chat_completion()")
    
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

