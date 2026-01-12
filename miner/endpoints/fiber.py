"""
Fiber MLTS endpoints for miner.

Handles encrypted challenge reception from validators.
"""

import json
import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status, Request, Response
from loguru import logger
from pydantic import BaseModel

from miner.config.config import Config
from miner.dependencies import get_config
from miner.network.fiber_server import FiberServer
from miner.endpoints.inference import inference, InferenceRequest

router = APIRouter(prefix="/fiber", tags=["Fiber"])

# Global FiberServer instance
fiber_server: Optional[FiberServer] = None


class PublicKeyResponse(BaseModel):
    public_key: str


class KeyExchangeRequest(BaseModel):
    encrypted_symmetric_key: str
    symmetric_key_uuid: str
    timestamp: float
    nonce: str
    signature: str
    validator_hotkey_ss58: str


class KeyExchangeResponse(BaseModel):
    success: bool
    message: str


def get_fiber_server_dependency(config: Config = Depends(get_config)) -> FiberServer:
    """Get or create FiberServer instance."""
    global fiber_server
    if fiber_server is None:
        fiber_server = FiberServer(config)
    return fiber_server


@router.get("/public-key", response_model=PublicKeyResponse, summary="Get Miner's RSA Public Key")
async def get_public_key(fiber: FiberServer = Depends(get_fiber_server_dependency)) -> PublicKeyResponse:
    """
    Returns the miner's RSA public key for Fiber handshake.
    """
    return PublicKeyResponse(public_key=fiber.get_public_key())


@router.post("/key-exchange", response_model=KeyExchangeResponse, summary="Exchange Symmetric Key")
async def key_exchange(
    request_data: KeyExchangeRequest,
    fiber: FiberServer = Depends(get_fiber_server_dependency)
) -> KeyExchangeResponse:
    """
    Receives an encrypted symmetric key from the validator and stores it.
    """
    success = await fiber.exchange_symmetric_key(
        encrypted_symmetric_key=request_data.encrypted_symmetric_key,
        symmetric_key_uuid=request_data.symmetric_key_uuid,
        timestamp=request_data.timestamp,
        nonce=request_data.nonce,
        signature=request_data.signature,
        validator_hotkey_ss58=request_data.validator_hotkey_ss58
    )
    
    if success:
        return KeyExchangeResponse(success=True, message="Symmetric key exchanged")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange symmetric key"
        )


@router.post("/challenge", summary="Receive Encrypted Challenge")
async def receive_encrypted_challenge(
    request: Request,
    validator_hotkey_ss58: str = Header(..., alias="x-fiber-validator-hotkey-ss58"),
    symmetric_key_uuid: str = Header(..., alias="x-fiber-symmetric-key-uuid"),
    fiber: FiberServer = Depends(get_fiber_server_dependency),
    config: Config = Depends(get_config)
) -> Response:
    """
    Receives an encrypted challenge payload, decrypts it, processes it via inference,
    and returns the inference response encrypted with the same symmetric key.
    """
    try:
        encrypted_payload = await request.body()
        decrypted_payload = await fiber.decrypt_challenge_payload(
            validator_hotkey_ss58=validator_hotkey_ss58,
            symmetric_key_uuid=symmetric_key_uuid,
            encrypted_payload=encrypted_payload
        )
        
        if not decrypted_payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to decrypt challenge payload or key expired/invalid."
            )
        
        # decrypted_payload is already a dict from decrypt_challenge_payload
        # Extract metadata before creating InferenceRequest (it may not accept metadata)
        challenge_metadata = None
        if isinstance(decrypted_payload, dict):
            challenge_metadata = decrypted_payload.pop('metadata', None)
        
        # Track timing: miner inference
        from miner.timing import PipelineTiming, PipelineStages
        
        # Try to extract timing data from challenge metadata if present
        pipeline_timing = None
        if challenge_metadata and 'timing_data' in challenge_metadata:
            try:
                timing_data = challenge_metadata['timing_data']
                if isinstance(timing_data, dict):
                    pipeline_timing = PipelineTiming.from_dict(timing_data)
            except Exception as e:
                logger.debug(f"Could not restore timing data: {e}")
        
        # Track miner inference stage
        if pipeline_timing:
            miner_inference_stage = pipeline_timing.add_stage(PipelineStages.MINER_INFERENCE)
        else:
            miner_inference_stage = None
        
        # Create inference request from decrypted payload (metadata already extracted)
        inference_request = InferenceRequest(**decrypted_payload)
        
        # Process the inference request
        response_data = await inference(
            request=inference_request,
            validator_hotkey=validator_hotkey_ss58,
            config=config
        )
        
        # Finish miner inference stage
        if pipeline_timing and miner_inference_stage:
            miner_inference_stage.finish()
        
        # Track miner response stage
        if pipeline_timing:
            miner_response_stage = pipeline_timing.add_stage(PipelineStages.MINER_RESPONSE)
        
        # Include timing data in response if available
        if pipeline_timing:
            if not isinstance(response_data, dict):
                response_data = dict(response_data) if hasattr(response_data, '__dict__') else {}
            if 'metadata' not in response_data:
                response_data['metadata'] = {}
            response_data['metadata']['timing_data'] = pipeline_timing.to_dict()
        
        if pipeline_timing and miner_response_stage:
            miner_response_stage.finish()
        
        # Encrypt the response using the same symmetric key
        if validator_hotkey_ss58 not in fiber._symmetric_key_cache:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symmetric key not found for response encryption"
            )
        
        if symmetric_key_uuid not in fiber._symmetric_key_cache[validator_hotkey_ss58]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symmetric key UUID not found for response encryption"
            )
        
        fernet_key, expiration_time = fiber._symmetric_key_cache[validator_hotkey_ss58][symmetric_key_uuid]
        
        if time.time() > expiration_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symmetric key expired for response encryption"
            )
        
        # Encrypt response
        response_json = json.dumps(response_data).encode('utf-8')
        encrypted_response = fernet_key.encrypt(response_json)
        
        logger.info(
            f"Received and processed encrypted challenge from {validator_hotkey_ss58[:8]}... "
            f"(UUID: {symmetric_key_uuid[:8]}...)"
        )
        
        # Return encrypted response as binary
        return Response(
            content=encrypted_response,
            media_type="application/octet-stream",
            headers={
                "x-fiber-symmetric-key-uuid": symmetric_key_uuid,
                "x-fiber-miner-hotkey-ss58": fiber.miner_hotkey.ss58_address if fiber.miner_hotkey else ""
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing encrypted challenge: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process encrypted challenge: {str(e)}"
        )

