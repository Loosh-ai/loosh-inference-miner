"""vLLM implementation using OpenAI-compatible API.

Note: OpenAI-compatible API does NOT mean it requires OpenAI models.
The vLLM server exposes an OpenAI-compatible REST API, but can serve any model
compatible with vLLM (HuggingFace models, local models, etc.). This uses the
OpenAI Python client library only for convenience in communicating with the API.
"""

from typing import Any, List, Dict, Optional, Union

from loguru import logger

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from miner.core.llms.LLMService import LLMService, LLMResponse


class VLLMService(LLMService):
    """LLM service using vLLM with OpenAI-compatible API.
    
    Note: Despite using the OpenAI client library, this does NOT require OpenAI models.
    vLLM exposes an OpenAI-compatible API that can serve any vLLM-supported model.
    """
    
    def __init__(self, config: Any):
        """Initialize vLLM service."""
        if AsyncOpenAI is None:
            raise ImportError(
                "openai is not installed. "
                "Install it with: pip install openai"
            )
        super().__init__(config)
        
        # Get vLLM server URL from config, default to localhost
        self.api_base = getattr(config, 'vllm_api_base', 'http://localhost:8000/v1')
        self.api_key = getattr(config, 'vllm_api_key', 'EMPTY')  # vLLM doesn't require real key
        
        # Initialize OpenAI client pointing to vLLM server
        # Note: We use the OpenAI Python library for convenience, but this connects to
        # the vLLM server (NOT OpenAI's API) and can serve any vLLM-compatible model.
        self.client = AsyncOpenAI(
            base_url=self.api_base,
            api_key=self.api_key
        )
        
        logger.info(f"Initialized vLLM service with API base: {self.api_base}")
    
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
        """Generate chat completion using vLLM OpenAI-compatible API.
        
        Note: OpenAI-compatible API means the interface follows OpenAI's API format,
        but this does NOT require OpenAI models. Any vLLM-supported model can be used.
        """
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
            
            # Call OpenAI-compatible API (connects to vLLM server, NOT OpenAI)
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
            logger.error(f"Error during chat completion with vLLM: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> str:
        """Verify model is available (vLLM handles model loading server-side).
        
        Args:
            model_name: Name/identifier of the model
            
        Returns:
            Model name (no actual model object needed for OpenAI-compatible API)
            
        Note: This does NOT require an OpenAI model. The vLLM server can load
        any vLLM-compatible model (HuggingFace, local models, etc.).
        """
        # vLLM server handles model loading, so we just return the model name
        # The model should be pre-loaded on the vLLM server
        return model_name
    
    async def health_check(self) -> bool:
        """Check if vLLM service is healthy."""
        try:
            if AsyncOpenAI is None:
                return False
            # Try to list models to verify server is accessible
            models = await self.client.models.list()
            return models is not None
        except Exception:
            return False

