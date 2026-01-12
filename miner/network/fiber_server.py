"""
Fiber MLTS (Multi-Layer Transport Security) server implementation for miner.

Provides RSA-based key exchange and symmetric key encryption for secure communication with validators.
"""

import asyncio
import json
import time
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from fiber.chain.chain_utils import load_hotkey_keypair
from miner.config.config import Config


class FiberServer:
    """
    Fiber server for handling secure key exchange and encrypted payloads from validators.
    
    Manages RSA keypair, symmetric key storage, and provides decryption capabilities.
    """
    
    def __init__(self, config: Config):
        """
        Initialize Fiber server.
        
        Args:
            config: Miner configuration
        """
        self.config = config
        self.key_ttl_seconds = config.fiber_key_ttl_seconds
        
        # Generate RSA keypair
        self._rsa_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self._rsa_public_key = self._rsa_private_key.public_key()
        
        # Cache for symmetric keys: {validator_hotkey_ss58: {uuid: (fernet_instance, expiration_time)}}
        self._symmetric_key_cache: Dict[str, Dict[str, Tuple[Fernet, float]]] = {}
        self._nonce_cache: Dict[str, float] = {}  # {nonce: timestamp} for replay protection
        
        # Load miner's hotkey for signature verification
        try:
            self.miner_hotkey = load_hotkey_keypair(
                config.wallet_name,
                config.hotkey_name
            )
            logger.info(f"FiberServer (Miner) initialized with hotkey: {self.miner_hotkey.ss58_address}")
        except Exception as e:
            logger.error(f"Failed to load miner hotkey for FiberServer: {e}")
            self.miner_hotkey = None
        
        # Background task for cleaning up expired keys (will be started on first use)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_started = False
    
    async def _cleanup_expired_keys(self):
        """Background task to clean up expired symmetric keys."""
        while True:
            await asyncio.sleep(self.key_ttl_seconds / 2)  # Check halfway through TTL
            now = time.time()
            
            for validator_hotkey, keys in list(self._symmetric_key_cache.items()):
                for uuid, (fernet_instance, expiration_time) in list(keys.items()):
                    if now > expiration_time:
                        logger.debug(f"Expiring symmetric key for validator {validator_hotkey[:8]}... (UUID: {uuid[:8]}...)")
                        del keys[uuid]
                if not keys:
                    del self._symmetric_key_cache[validator_hotkey]
            
            # Clean nonce cache
            for nonce, timestamp in list(self._nonce_cache.items()):
                if now - timestamp > self.config.fiber_handshake_timeout_seconds:
                    del self._nonce_cache[nonce]
    
    def _ensure_cleanup_task_started(self):
        """Start cleanup task if not already started (lazy initialization)."""
        if not self._cleanup_started:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_expired_keys())
                self._cleanup_started = True
                logger.debug("Started background cleanup task for expired keys")
            except RuntimeError:
                # No running event loop - task will be started on first async call
                logger.debug("No running event loop - cleanup task will start on first async call")
                pass
    
    def get_public_key(self) -> str:
        """Get RSA public key in PEM format."""
        pem = self._rsa_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')
    
    async def exchange_symmetric_key(
        self,
        encrypted_symmetric_key: str,
        symmetric_key_uuid: str,
        timestamp: float,
        nonce: str,
        signature: str,
        validator_hotkey_ss58: str
    ) -> bool:
        """
        Exchange symmetric key with validator.
        
        Args:
            encrypted_symmetric_key: Hex-encoded RSA-encrypted symmetric key
            symmetric_key_uuid: Unique identifier for this symmetric key
            timestamp: Timestamp for anti-replay protection
            nonce: Nonce for anti-replay protection
            signature: Signature from validator (for verification)
            validator_hotkey_ss58: Validator's SS58 address (hotkey)
        
        Returns:
            True if key exchange successful, False otherwise
        """
        self._ensure_cleanup_task_started()
        try:
            # Replay protection
            if nonce in self._nonce_cache and \
               time.time() - self._nonce_cache[nonce] < self.config.fiber_handshake_timeout_seconds:
                logger.warning(f"Replay attack detected for nonce: {nonce}")
                return False
            self._nonce_cache[nonce] = time.time()
            
            # TODO: Verify signature using validator's public key from metagraph
            # For now, we'll trust the validator_hotkey_ss58
            
            # Decrypt symmetric key
            encrypted_key_bytes = bytes.fromhex(encrypted_symmetric_key)
            symmetric_key_bytes = self._rsa_private_key.decrypt(
                encrypted_key_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            fernet_key = Fernet(symmetric_key_bytes)
            
            expiration_time = time.time() + self.key_ttl_seconds
            
            if validator_hotkey_ss58 not in self._symmetric_key_cache:
                self._symmetric_key_cache[validator_hotkey_ss58] = {}
            
            self._symmetric_key_cache[validator_hotkey_ss58][symmetric_key_uuid] = (fernet_key, expiration_time)
            
            logger.info(f"Symmetric key exchanged successfully with validator {validator_hotkey_ss58[:8]}... (UUID: {symmetric_key_uuid[:8]}...)")
            return True
            
        except InvalidToken:
            logger.error("Invalid token during symmetric key decryption.")
            return False
        except Exception as e:
            logger.error(f"Error during symmetric key exchange: {e}", exc_info=True)
            return False
    
    async def decrypt_challenge_payload(
        self,
        validator_hotkey_ss58: str,
        symmetric_key_uuid: str,
        encrypted_payload: bytes
    ) -> Optional[Dict]:
        """Decrypt challenge payload from validator."""
        self._ensure_cleanup_task_started()
        
        """
        Decrypt challenge payload from validator.
        
        Args:
            validator_hotkey_ss58: Validator's SS58 address
            symmetric_key_uuid: UUID of the symmetric key to use
            encrypted_payload: Encrypted challenge payload
        
        Returns:
            Decrypted payload as dictionary, or None if decryption fails
        """
        try:
            if validator_hotkey_ss58 not in self._symmetric_key_cache:
                logger.warning(f"No symmetric keys found for validator: {validator_hotkey_ss58[:8]}...")
                return None
            
            if symmetric_key_uuid not in self._symmetric_key_cache[validator_hotkey_ss58]:
                logger.warning(f"Symmetric key UUID {symmetric_key_uuid[:8]}... not found for validator: {validator_hotkey_ss58[:8]}...")
                return None
            
            fernet_key, expiration_time = self._symmetric_key_cache[validator_hotkey_ss58][symmetric_key_uuid]
            
            if time.time() > expiration_time:
                logger.warning(f"Symmetric key for validator {validator_hotkey_ss58[:8]}... (UUID: {symmetric_key_uuid[:8]}...) has expired.")
                del self._symmetric_key_cache[validator_hotkey_ss58][symmetric_key_uuid]
                return None
            
            decrypted_payload = fernet_key.decrypt(encrypted_payload, ttl=self.key_ttl_seconds).decode('utf-8')
            return json.loads(decrypted_payload)
            
        except InvalidToken:
            logger.error(f"Invalid token for validator {validator_hotkey_ss58[:8]}..., UUID {symmetric_key_uuid[:8]}... - payload decryption failed.")
            return None
        except Exception as e:
            logger.error(f"Error decrypting challenge payload: {e}", exc_info=True)
            return None


