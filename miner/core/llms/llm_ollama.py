"""Ollama implementation using OpenAI-compatible API.

Note: OpenAI-compatible API does NOT mean it requires OpenAI models.
The Ollama server exposes an OpenAI-compatible REST API, but serves models installed locally in Ollama.
This uses the OpenAI Python client library only for convenience in communicating with the API.
"""

from typing import Any, List, Dict, Optional, Union

from loguru import logger

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from miner.core.llms.LLMService import LLMService, LLMResponse


class OllamaService(LLMService):
    """LLM service using Ollama with OpenAI-compatible API.
    
    Note: Despite using the OpenAI client library, this does NOT require OpenAI models.
    Ollama exposes an OpenAI-compatible API that serves models installed in Ollama (llama, mistral, etc.).
    """
    
    def __init__(self, config: Any):
        """Initialize Ollama service."""
        if AsyncOpenAI is None:
            raise ImportError(
                "openai is not installed. "
                "Install it with: pip install openai"
            )
        super().__init__(config)
        
        # Get Ollama base URL from config, default to localhost
        ollama_host = getattr(config, 'ollama_host', 'localhost')
        ollama_port = getattr(config, 'ollama_port', 11434)
        self.api_base = getattr(
            config, 
            'ollama_api_base', 
            f"http://{ollama_host}:{ollama_port}/v1"
        )
        self.api_key = getattr(config, 'ollama_api_key', 'ollama')  # Ollama doesn't require real key
        
        # Initialize OpenAI client pointing to Ollama server
        # Note: We use the OpenAI Python library for convenience, but this connects to
        # the Ollama server (NOT OpenAI's API) and serves models installed in Ollama.
        self.client = AsyncOpenAI(
            base_url=self.api_base,
            api_key=self.api_key
        )
        
        logger.info(f"Initialized Ollama service with API base: {self.api_base}")
    
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
        """Generate chat completion using Ollama OpenAI-compatible API.
        
        Note: OpenAI-compatible API means the interface follows OpenAI's API format,
        but this does NOT require OpenAI models. This serves models installed in Ollama.
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
            
            # Call OpenAI-compatible API (connects to Ollama server, NOT OpenAI)
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
            logger.error(f"Error during chat completion with Ollama: {str(e)}")
            raise
    
    async def _get_model(self, model_name: str) -> str:
        """Verify model is available in Ollama.
        
        This doesn't actually load the model, but checks if it's available.
        
        Args:
            model_name: Name/identifier of the model
            
        Returns:
            Model name (Ollama handles model loading server-side)
        """
        try:
            # Try to list models to verify server is accessible
            models = await self.client.models.list()
            model_names = [m.id for m in models.data]
            
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
            if AsyncOpenAI is None:
                return False
            # Try to list models to verify server is accessible
            models = await self.client.models.list()
            return models is not None
        except Exception:
            return False

