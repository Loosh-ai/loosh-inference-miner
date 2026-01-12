from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

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
) -> Dict[str, Any]:
    """
    Check if the miner is available.
    
    Accepts optional validator-hotkey header for logging purposes.
    """
    # Extract validator hotkey from headers (case-insensitive)
    validator_hotkey = None
    for header_name, header_value in request.headers.items():
        if header_name.lower() == "validator-hotkey":
            validator_hotkey = header_value
            break
    
    # Log if validator hotkey is provided (for debugging)
    if validator_hotkey:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Availability check from validator: {validator_hotkey[:8]}...")
    
    return AvailabilityResponse().model_dump() 