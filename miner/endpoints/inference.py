import time
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from miner.config.config import Config
from miner.core.llms import get_backend
from miner.core.llms.LLMService import LLMResponse as LLMServiceResponse

router = APIRouter()


class TokenUsage(BaseModel):
    """Token usage statistics for cost attribution (F3)."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class InferenceRequest(BaseModel):
    """
    Request for LLM inference.
    
    Supports both legacy prompt-based and OpenAI-compatible message-based formats.
    """
    # Legacy prompt (backward compatible)
    prompt: Optional[str] = None
    
    # OpenAI-compatible message format (preferred)
    messages: Optional[List[Dict[str, Any]]] = None
    
    # Model and generation parameters
    # Note: model is optional - miner uses its configured DEFAULT_MODEL
    # Validators may send a model name but miners control what they serve
    model: Optional[str] = None
    max_tokens: int
    temperature: float
    top_p: float
    
    # Tool calling support
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Tool definitions for function calling")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice: 'auto', 'none', or specific tool")


class InferenceResponse(BaseModel):
    """
    Response from LLM inference with usage tracking.
    
    Includes token usage for cost attribution (F3).
    """
    response_text: str
    response_time_ms: int
    
    # Tool calling support
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "stop"
    
    # Token usage (REQUIRED for cost tracking - F3)
    usage: TokenUsage = Field(default_factory=TokenUsage)

def get_config_dependency():
    """Get config for dependency injection."""
    from miner.dependencies import get_config
    return get_config()

@router.post("")
async def inference(
    request: InferenceRequest,
    validator_hotkey: str = Header(..., alias="validator-hotkey"),
    config: Config = Depends(get_config_dependency)
) -> Dict[str, Any]:
    """
    Handle inference request (DEPRECATED - Use Fiber MLTS /fiber/challenge endpoint instead).
    
    This endpoint is deprecated in favor of the Fiber-encrypted /fiber/challenge endpoint.
    New validators should use Fiber MLTS for secure communication.
    
    Supports both legacy prompt-based and OpenAI-compatible message-based formats.
    Returns token usage for cost attribution (F3).
    """
    try:
        # Initialize LLM service if not already initialized
        if not hasattr(router, "llm_service"):
            backend_name = getattr(config, 'llm_backend', 'llamacpp')
            try:
                router.llm_service = get_backend(backend_name, config)
            except KeyError as e:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"LLM backend '{backend_name}' is not available. "
                        f"Available backends may be limited. "
                        f"Check that required dependencies are installed. "
                        f"Error: {str(e)}"
                    )
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Failed to initialize LLM backend '{backend_name}': {str(e)}. "
                        f"Please check your LLM configuration and ensure the backend is properly installed."
                    )
                )
        
        # Start timing
        start_time = time.time()
        
        # Determine if we should use messages or prompt
        # Messages take precedence over prompt (OpenAI-compatible)
        messages = request.messages
        if messages is None and request.prompt:
            # Convert legacy prompt to messages format
            messages = [{"role": "user", "content": request.prompt}]
        elif messages is None:
            raise HTTPException(
                status_code=400,
                detail="Either 'prompt' or 'messages' must be provided"
            )
        
        # Use miner's configured model, not what validator sends
        # This ensures the miner uses the model it has loaded (e.g., in vLLM)
        # Validators may send a model name, but miners control what they serve
        model_to_use = config.default_model
        
        # Generate response using chat_completion for full feature support
        llm_response: LLMServiceResponse = await router.llm_service.chat_completion(
            messages=messages,
            model=model_to_use,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            tools=request.tools,
            tool_choice=request.tool_choice
        )
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Build response with usage tracking (F3)
        return InferenceResponse(
            response_text=llm_response.content,
            response_time_ms=response_time_ms,
            tool_calls=llm_response.tool_calls,
            finish_reason=llm_response.finish_reason,
            usage=TokenUsage(
                prompt_tokens=llm_response.usage.prompt_tokens,
                completion_tokens=llm_response.usage.completion_tokens,
                total_tokens=llm_response.usage.total_tokens
            )
        ).model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during inference: {str(e)}"
        ) 