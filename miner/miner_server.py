"""
Miner FastAPI server using uvicorn.

Runs the miner as a FastAPI application. Subnet registration is handled
separately using Fiber's fiber-post-ip command.
"""

import os
import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI

from miner.config.config import Config
from miner.dependencies import get_config
from miner.endpoints.inference import router as inference_router
from miner.endpoints.availability import router as availability_router
from miner.endpoints.fiber import router as fiber_router


def get_config_dependency():
    """Get config for dependency injection."""
    return get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    from miner.main import main_loop
    main_loop_task = asyncio.create_task(main_loop())
    yield
    # Shutdown
    main_loop_task.cancel()
    try:
        await main_loop_task
    except asyncio.CancelledError:
        pass


# Create FastAPI app
app = FastAPI(
    title="Loosh Inference Miner",
    description="Bittensor subnet miner for LLM inference with Fiber MLTS encryption. Register on subnet using fiber-post-ip command.",
    lifespan=lifespan
)

# Add dependencies
app.dependency_overrides[Config] = get_config_dependency

# API Endpoints

# /inference (deprecated - use /fiber/challenge instead)
app.include_router(
    inference_router,
    prefix="/inference",
    tags=["inference"]
)

# /availability
app.include_router(
    availability_router,
    prefix="/availability",
    tags=["availability"]
)

# /fiber (MLTS secure communication)
app.include_router(
    fiber_router,
    tags=["Fiber"]
)


if __name__ == "__main__":
    import uvicorn
    config = get_config_dependency()
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port
    )

