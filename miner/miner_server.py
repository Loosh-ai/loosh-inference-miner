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

# Global concurrency control
_request_semaphore: asyncio.Semaphore = None
_active_requests: set = set()
_pending_requests_queue: asyncio.Queue = None


def get_config_dependency():
    """Get config for dependency injection."""
    return get_config()


def get_request_semaphore() -> asyncio.Semaphore:
    """Get the global request semaphore."""
    return _request_semaphore


def get_active_requests() -> set:
    """Get the set of active request tasks."""
    return _active_requests


def get_pending_requests_queue() -> asyncio.Queue:
    """Get the global pending requests queue."""
    return _pending_requests_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _request_semaphore, _pending_requests_queue
    
    # Startup
    config = get_config()
    max_concurrent = config.max_concurrent_requests
    _request_semaphore = asyncio.Semaphore(max_concurrent)
    _pending_requests_queue = asyncio.Queue()
    
    from loguru import logger
    logger.info(f"Miner concurrency limit: {max_concurrent} concurrent requests")
    
    # Background task to process pending requests FIFO
    async def process_pending_requests():
        """Process pending requests from queue when capacity becomes available (FIFO)."""
        from loguru import logger
        while True:
            try:
                # Wait for a pending request (with timeout to check if still running)
                try:
                    pending_request_data = await asyncio.wait_for(
                        _pending_requests_queue.get(),
                        timeout=1.0  # Check every second
                    )
                except asyncio.TimeoutError:
                    continue  # No pending requests, continue loop
                
                # Acquire semaphore (will wait if at capacity, ensuring FIFO processing)
                async with _request_semaphore:
                    # Capacity available, process the request
                    logger.debug(
                        f"Processing queued request (queue size: {_pending_requests_queue.qsize()}, "
                        f"active: {len(_active_requests)})"
                    )
                    
                    # Create task to process the request
                    async def process_with_result():
                        """Process request and set result in future."""
                        try:
                            result = await pending_request_data['process_func']()
                            if not pending_request_data['result_future'].done():
                                pending_request_data['result_future'].set_result(result)
                        except Exception as e:
                            if not pending_request_data['result_future'].done():
                                pending_request_data['result_future'].set_exception(e)
                    
                    task = asyncio.create_task(process_with_result())
                    _active_requests.add(task)
                    task.add_done_callback(_active_requests.discard)
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)
            except Exception as e:
                from loguru import logger
                logger.error(f"Error in pending requests processor: {e}", exc_info=True)
                await asyncio.sleep(1.0)
    
    # Start pending requests processor
    pending_task = asyncio.create_task(process_pending_requests())
    
    from miner.main import main_loop
    main_loop_task = asyncio.create_task(main_loop())
    yield
    # Shutdown
    pending_task.cancel()
    try:
        await pending_task
    except asyncio.CancelledError:
        pass
    
    main_loop_task.cancel()
    try:
        await main_loop_task
    except asyncio.CancelledError:
        pass
    
    # Wait for active requests to complete
    if _active_requests:
        from loguru import logger
        logger.info(f"Waiting for {len(_active_requests)} active request(s) to complete...")
        await asyncio.gather(*_active_requests, return_exceptions=True)


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

