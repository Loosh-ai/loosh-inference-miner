from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from miner.config.config import Config

router = APIRouter()

class AvailabilityResponse(BaseModel):
    """Response for availability check."""
    available: bool = True

def get_config_dependency():
    """Get config for dependency injection."""
    from miner.dependencies import get_config
    return get_config()

@router.get("")
async def check_availability(
    request: Request,
    config: Config = Depends(get_config_dependency)
) -> JSONResponse:
    """
    Check if the miner is available.
    
    This endpoint is used by validators to check if the miner is ready
    to accept inference challenges. Returns available=True only when
    the miner is fully initialized and ready to process requests.
    
    Accepts optional validator-hotkey header for logging purposes.
    
    Returns:
        JSONResponse with {"available": true/false} and appropriate HTTP status
    """
    try:
        # Check if miner is fully initialized (semaphore and queue ready)
        from miner.miner_server import get_request_semaphore, get_pending_requests_queue
        
        request_semaphore = get_request_semaphore()
        pending_queue = get_pending_requests_queue()
        
        if not request_semaphore or not pending_queue:
            logger.debug("Miner not fully initialized - returning unavailable")
            return JSONResponse(
                content={"available": False, "reason": "Miner initializing"},
                status_code=status.HTTP_200_OK  # Return 200 so validators know we're reachable but not ready
            )
        
        # Extract validator hotkey from headers (case-insensitive)
        validator_hotkey = None
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "validator-hotkey":
                validator_hotkey = header_value
                break
        
        # Log availability check (for debugging and monitoring)
        if validator_hotkey:
            logger.debug(f"Availability check from validator: {validator_hotkey[:8]}...")
        else:
            logger.debug("Availability check from unknown validator")
        
        # Miner is fully initialized and ready
        # Use model_dump() for Pydantic v2, fallback to dict() for v1
        try:
            response_obj = AvailabilityResponse()
            if hasattr(response_obj, 'model_dump'):
                response_data = response_obj.model_dump()
            else:
                # Pydantic v1 compatibility
                response_data = response_obj.dict()
        except Exception:
            # Fallback to manual dict
            response_data = {"available": True}
        
        logger.debug(f"Returning availability response: {response_data}")
        
        # Return JSON response with explicit status code
        return JSONResponse(
            content=response_data,
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        # If there's an error, log it but still return available=False
        # This allows validators to know the miner is reachable but not ready
        logger.error(f"Error in availability check: {e}", exc_info=True)
        return JSONResponse(
            content={"available": False, "error": str(e)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        ) 