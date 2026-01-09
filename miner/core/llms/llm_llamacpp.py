"""llama.cpp implementation using OpenAI-compatible API."""

from typing import Any, List, Dict, Optional, Union

from loguru import logger

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from miner.core.llms.LLMService import LLMService, LLMResponse


class LlamaCppService(LLMService):
    """LLM service using llama-cpp-python with OpenAI-compatible API."""
    
    def __init__(self, config: Any):
        """Initialize llama.cpp service."""
        if AsyncOpenAI is None:
            raise ImportError(
                "openai is not installed. "
                "Install it with: pip install openai"
            )
        super().__init__(config)
        
        # Get llama.cpp server URL from config, default to localhost
        # llama-cpp-python's OpenAI-compatible server typically runs on port 8080
        self.api_base = getattr(config, 'llamacpp_api_base', 'http://localhost:8080/v1')
        self.api_key = getattr(config, 'llamacpp_api_key', 'EMPTY')  # llama.cpp doesn't require real key
        
        # Initialize OpenAI client pointing to llama.cpp server
        self.client = AsyncOpenAI(
            base_url=self.api_base,
            api_key=self.api_key
        )
        
        logger.info(f"Initialized llama.cpp service with API base: {self.api_base}")
        logger.warning(
            "Note: llama.cpp OpenAI-compatible server must be running separately. "
            "Start it with: python -m llama_cpp.server --model <model_path>"
        )
    
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
        """Generate chat completion using llama.cpp OpenAI-compatible API."""
        try:
            # Prepare request parameters
            request_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
            }
            
            # Add tools if provided
            if tools is not None:
                request_params["tools"] = tools
                if tool_choice is not None:
                    request_params["tool_choice"] = tool_choice
            
            # Call OpenAI-compatible API
            response = await self.client.chat.completions.create(**request_params)
            
            # Extract content and tool calls
            choice = response.choices[0]
            content = choice.message.content or ""
            
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in choice.message.tool_calls
                ]
            
            return LLMResponse(content=content, tool_calls=tool_calls)
            
        except Exception as e:
            logger.error(f"Error during chat completion with llama.cpp: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> str:
        """Verify model is available (llama.cpp handles model loading server-side).
        
        Args:
            model_name: Name/identifier of the model
            
        Returns:
            Model name (no actual model object needed for OpenAI API)
        """
        # llama.cpp server handles model loading, so we just return the model name
        # The model should be pre-loaded on the llama.cpp server
        return model_name
    
    async def health_check(self) -> bool:
        """Check if llama.cpp service is healthy."""
        try:
            if AsyncOpenAI is None:
                return False
            # Try to list models to verify server is accessible
            models = await self.client.models.list()
            return models is not None
        except Exception:
            return False

