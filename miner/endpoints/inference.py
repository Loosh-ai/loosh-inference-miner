import asyncio
import random
import time
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from miner.config.config import Config
from miner.core.llms import get_backend
from miner.core.llms.LLMService import LLMResponse as LLMServiceResponse

router = APIRouter()

# Random phrases for test mode responses to help differentiate miners
# Some phrases are semantically similar but use different words to test similarity detection
TEST_MODE_PHRASES = [
    # Unique phrases
    "The quick brown fox jumps over the lazy dog.",
    "In a galaxy far, far away, there exists infinite possibilities.",
    "The ocean waves crash against the shore with rhythmic precision.",
    "Mountains stand tall as silent witnesses to time's passage.",
    "Stars twinkle in the night sky like distant dreams.",
    "Nature's beauty unfolds in every season's unique tapestry.",
    "Knowledge is the key that unlocks the doors of understanding.",
    "The ancient forest whispers secrets to those who listen carefully.",
    "Desert sands shift endlessly under the relentless sun.",
    "Rivers flow ceaselessly toward the vast and waiting sea.",
    
    # Semantically similar pairs (different words, similar meaning)
    # Pair 1: AI/Technology evolution
    "Artificial intelligence continues to evolve and transform our world.",
    "Machine learning systems progressively develop and reshape human society.",
    
    # Pair 2: Quantum physics
    "Quantum mechanics reveals the mysterious nature of reality.",
    "Subatomic physics uncovers the enigmatic essence of existence.",
    
    # Pair 3: Technology connectivity
    "Technology connects humanity across vast digital landscapes.",
    "Digital networks link people together through expansive virtual realms.",
    
    # Pair 4: Learning/Understanding
    "Education opens pathways to new realms of comprehension.",
    "Learning creates bridges to previously unknown territories of insight.",
    
    # Pair 5: Time and change
    "Time marches forward, leaving transformation in its wake.",
    "The passage of years brings inevitable change to all things.",
    
    # Pair 6: Nature's cycles
    "Seasons change in an eternal dance of renewal and decay.",
    "The natural world cycles through patterns of growth and decline."
]


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
        # Check if test mode is enabled
        test_mode = getattr(config, 'test_mode', False)
        
        if test_mode:
            # Test mode: return success message without running inference
            start_time = time.time()
            # Simulate minimal processing time
            await asyncio.sleep(0.01)  # 10ms delay to simulate processing
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Select a random phrase to add variation to test mode responses
            random_phrase = random.choice(TEST_MODE_PHRASES)
            
            # Estimate token usage for test mode (approximate)
            test_response_text = f"[TEST MODE] Inference request received successfully. Test mode is enabled - no actual inference was performed. {random_phrase}"
            prompt_text = request.prompt or ""
            if request.messages:
                prompt_text = " ".join(m.get("content", "") for m in request.messages if m.get("content"))
            
            # Rough estimation: ~4 chars per token
            estimated_prompt_tokens = max(1, len(prompt_text) // 4)
            estimated_completion_tokens = max(1, len(test_response_text) // 4)
            
            return InferenceResponse(
                response_text=test_response_text,
                response_time_ms=response_time_ms,
                finish_reason="stop",
                usage=TokenUsage(
                    prompt_tokens=estimated_prompt_tokens,
                    completion_tokens=estimated_completion_tokens,
                    total_tokens=estimated_prompt_tokens + estimated_completion_tokens
                )
            ).model_dump()
        
        # Normal mode: run actual inference
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