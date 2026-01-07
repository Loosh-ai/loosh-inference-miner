from typing import Dict, Any

from fastapi import APIRouter, Depends, Header
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
    validator_hotkey: str = Header(..., alias="validator-hotkey"),
    config: Config = Depends(get_config_dependency)
) -> Dict[str, Any]:
    """Check if the miner is available."""
    return AvailabilityResponse().model_dump() 