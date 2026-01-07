import asyncio
import time
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from miner.config.config import Config
from miner.core.llms import get_backend

router = APIRouter()

class InferenceRequest(BaseModel):
    """Request for LLM inference."""
    prompt: str
    model: str
    max_tokens: int
    temperature: float
    top_p: float

class InferenceResponse(BaseModel):
    """Response from LLM inference."""
    response_text: str
    response_time_ms: int

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
    """Handle inference request."""
    try:
        # Check if test mode is enabled
        test_mode = getattr(config, 'test_mode', False)
        
        if test_mode:
            # Test mode: return success message without running inference
            start_time = time.time()
            # Simulate minimal processing time
            await asyncio.sleep(0.01)  # 10ms delay to simulate processing
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return InferenceResponse(
                response_text="[TEST MODE] Inference request received successfully. Test mode is enabled - no actual inference was performed.",
                response_time_ms=response_time_ms
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
        
        # Generate response
        response_text = await router.llm_service.generate(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        )
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        return InferenceResponse(
            response_text=response_text,
            response_time_ms=response_time_ms
        ).model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during inference: {str(e)}"
        ) 