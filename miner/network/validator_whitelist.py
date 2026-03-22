"""
Validator hotkey whitelist for DDoS mitigation.

Maintains a set of known validator hotkeys from the metagraph and optionally
from the Challenge API. Requests from unknown hotkeys are rejected early
before any expensive crypto operations.
"""

import asyncio
import time
from typing import Any, Optional, Set

import httpx
from loguru import logger

from miner.config.config import Config
from miner.network.challenge_api_auth import merge_auth_headers


class ValidatorWhitelist:
    """
    Maintains an allowlist of validator hotkeys sourced from the Bittensor
    metagraph (on-chain) and optionally from the Challenge API.

    The whitelist is refreshed periodically in a background task. Endpoints
    can call ``is_allowed()`` to gate requests before performing any
    expensive work (RSA decryption, inference, etc.).

    When the whitelist is empty (e.g. on first start before the first
    metagraph sync completes), all hotkeys are allowed to avoid a bootstrap
    deadlock.
    """

    METAGRAPH_REFRESH_INTERVAL_SEC: int = 300
    CHALLENGE_API_POLL_INTERVAL_SEC: int = 300

    def __init__(self, config: Config, keypair: Optional[Any] = None):
        self._config = config
        self._keypair = keypair
        self._metagraph_hotkeys: Set[str] = set()
        self._challenge_api_hotkeys: Set[str] = set()
        self._validator_ips: Set[str] = set()
        self._last_metagraph_refresh: float = 0.0
        self._last_challenge_api_poll: float = 0.0
        self._refresh_task: Optional[asyncio.Task] = None
        self._started = False

    @property
    def allowed_hotkeys(self) -> Set[str]:
        """Union of metagraph and Challenge API validator hotkeys."""
        return self._metagraph_hotkeys | self._challenge_api_hotkeys

    @property
    def is_populated(self) -> bool:
        """True once at least one successful refresh has occurred."""
        return len(self.allowed_hotkeys) > 0

    @property
    def validator_ips(self) -> Set[str]:
        """Known validator IPs from the Challenge API (updated each poll cycle)."""
        return self._validator_ips

    def is_allowed(self, hotkey_ss58: str) -> bool:
        """
        Check whether a hotkey is in the whitelist.

        Returns True if:
        - The hotkey is in the whitelist, OR
        - The whitelist is empty (bootstrap grace period).
        """
        if not self.is_populated:
            return True
        return hotkey_ss58 in self.allowed_hotkeys

    async def refresh_metagraph(self) -> None:
        """Fetch validator hotkeys from the metagraph."""
        try:
            from fiber.chain.fetch_nodes import get_nodes_for_netuid
            from fiber.chain.interface import get_substrate

            substrate = get_substrate(
                subtensor_network=self._config.subtensor_network,
                subtensor_address=self._config.subtensor_address,
            )
            nodes = get_nodes_for_netuid(
                substrate=substrate,
                netuid=self._config.netuid,
            )

            validator_hotkeys: Set[str] = set()
            for node in nodes:
                if getattr(node, "validator_permit", False):
                    validator_hotkeys.add(node.hotkey)

            old_count = len(self._metagraph_hotkeys)
            self._metagraph_hotkeys = validator_hotkeys
            self._last_metagraph_refresh = time.time()

            if len(validator_hotkeys) != old_count:
                logger.info(
                    f"Validator whitelist refreshed from metagraph: "
                    f"{len(validator_hotkeys)} validators (was {old_count})"
                )
            else:
                logger.debug(
                    f"Validator whitelist refreshed from metagraph: "
                    f"{len(validator_hotkeys)} validators (unchanged)"
                )
        except Exception as e:
            logger.error(f"Failed to refresh validator whitelist from metagraph: {e}")

    async def poll_challenge_api(self) -> None:
        """
        Fetch active validator hotkeys from the Challenge API.

        Authenticates with sr25519 hotkey signature (same scheme as
        validators).  Falls back to ``X-API-Key`` if no keypair is
        available, for backward compatibility with older deployments.

        Requires ``challenge_api_url`` to be set in the miner config.
        Silently skips if not configured.
        """
        challenge_api_url = getattr(self._config, "challenge_api_url", None)
        if not challenge_api_url:
            logger.info("Challenge API poll skipped: challenge_api_url not configured")
            return

        challenge_api_key = getattr(self._config, "challenge_api_key", None)

        try:
            headers = merge_auth_headers(
                {},
                body=None,
                keypair=self._keypair,
                api_key=challenge_api_key,
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{challenge_api_url}/validators/active-hotkeys",
                    headers=headers,
                )
                resp.raise_for_status()

            data = resp.json()
            hotkeys: Set[str] = set()
            ips: Set[str] = set()
            for entry in data:
                if isinstance(entry, dict):
                    hotkeys.add(entry["hotkey_ss58"])
                    ip = entry.get("ip")
                    if ip:
                        ips.add(ip)
                elif isinstance(entry, str):
                    hotkeys.add(entry)

            old_count = len(self._challenge_api_hotkeys)
            self._challenge_api_hotkeys = hotkeys
            self._validator_ips = ips
            self._last_challenge_api_poll = time.time()

            logger.info(
                f"Validator whitelist updated from Challenge API: "
                f"{len(hotkeys)} active validators, {len(ips)} IPs (was {old_count})"
            )
        except httpx.HTTPStatusError as e:
            logger.info(
                f"Challenge API active-hotkeys returned {e.response.status_code} — "
                f"skipping (endpoint may not be deployed yet)"
            )
        except Exception as e:
            logger.info(f"Challenge API poll skipped: {e}")

    async def _refresh_loop(self) -> None:
        """Background loop that periodically refreshes both sources."""
        # Initial metagraph sync on startup
        await self.refresh_metagraph()
        await self.poll_challenge_api()

        while True:
            try:
                await asyncio.sleep(self.METAGRAPH_REFRESH_INTERVAL_SEC)
                await self.refresh_metagraph()
                await self.poll_challenge_api()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in validator whitelist refresh loop: {e}")
                await asyncio.sleep(30)

    def start(self) -> None:
        """Start the background refresh task (must be called within a running event loop)."""
        if self._started:
            return
        try:
            loop = asyncio.get_running_loop()
            self._refresh_task = loop.create_task(self._refresh_loop())
            self._started = True
            logger.info("Validator whitelist background refresh started")
        except RuntimeError:
            logger.debug(
                "No running event loop — validator whitelist will start on first use"
            )

    def stop(self) -> None:
        """Cancel the background refresh task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            self._started = False
