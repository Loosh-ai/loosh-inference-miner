"""
Hotkey-signature authentication for outbound requests to the Challenge API.

Miners sign each request with their sr25519 hotkey using the same scheme
as validators/Fiber (nonce + hotkey + SHA-256 body hash).  This eliminates
the need for shared API keys — the miner's on-chain identity is the credential.

The Challenge API verifies the signature and checks that the hotkey belongs
to a registered node on the subnet.

Usage
-----
    from miner.network.challenge_api_auth import get_auth_headers

    headers = get_auth_headers(body=None, keypair=miner_keypair)
    # → {"X-Hotkey": "5G...", "X-Nonce": "...", "X-Signature": "0x..."}

Backwards compatibility
-----------------------
If no keypair is provided, ``get_auth_headers`` returns an empty dict so
callers can fall through to legacy API-key authentication without crashing.
"""

import hashlib
import time
from typing import Any, Dict, Optional

from loguru import logger


def get_auth_headers(
    body: Optional[bytes] = None,
    *,
    keypair: Optional[Any] = None,
) -> Dict[str, str]:
    """Build hotkey-signature auth headers for a Challenge API request.

    Parameters
    ----------
    body : bytes | None
        Raw request body (JSON-encoded).  For GET requests pass ``None``.
    keypair : Keypair | None
        The miner's sr25519 keypair (``substrateinterface.Keypair``).

    Returns
    -------
    dict
        ``{"X-Hotkey": ..., "X-Nonce": ..., "X-Signature": ...}`` on
        success, or an **empty dict** if no keypair is available (allows
        callers to fall back to API-key auth).
    """
    if keypair is None:
        return {}

    try:
        nonce = str(time.time())
        hotkey_ss58: str = keypair.ss58_address

        if body:
            body_hash = hashlib.sha256(body).hexdigest()
            message = f"{nonce}:{hotkey_ss58}:{body_hash}"
        else:
            message = f"{nonce}:{hotkey_ss58}"

        sig_bytes = keypair.sign(message)
        signature = f"0x{sig_bytes.hex()}"

        return {
            "X-Hotkey": hotkey_ss58,
            "X-Nonce": nonce,
            "X-Signature": signature,
        }
    except Exception as e:
        logger.warning(f"Failed to generate hotkey auth headers: {e}")
        return {}


def merge_auth_headers(
    existing_headers: Dict[str, str],
    body: Optional[bytes] = None,
    *,
    api_key: Optional[str] = None,
    keypair: Optional[Any] = None,
) -> Dict[str, str]:
    """Return *existing_headers* enriched with authentication.

    Tries hotkey signature first.  If that is unavailable (no keypair) and
    an ``api_key`` is provided, falls back to ``X-API-Key``.

    During rollout both headers are sent so the miner works against older
    Challenge API deployments that only check ``X-API-Key``.
    """
    auth = get_auth_headers(body=body, keypair=keypair)
    headers = dict(existing_headers)

    if auth:
        headers.update(auth)
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    if api_key:
        headers["X-API-Key"] = api_key
        return headers

    return headers
