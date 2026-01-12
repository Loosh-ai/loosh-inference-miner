"""
Miner background tasks.

Note: Subnet registration is handled by Fiber using the fiber-post-ip command.
This module provides a minimal background loop placeholder if needed.
"""

import asyncio
from loguru import logger

from miner.config.shared_config import get_miner_config


async def main_loop():
    """
    Background loop for the miner.
    
    Note: Subnet registration should be done separately using:
    fiber-post-ip --netuid <NETUID> --subtensor.network <NETWORK> \
        --external_port <PORT> --wallet.name <WALLET> --wallet.hotkey <HOTKEY> \
        --external_ip <IP>
    
    This function currently just keeps the background task alive.
    """
    try:
        config = get_miner_config()
        logger.info(
            f"Miner background loop started. "
            f"Wallet: {config.wallet.wallet_name}, Hotkey: {config.wallet.hotkey_name}"
        )
        logger.info(
            f"Note: Register on subnet using: "
            f"fiber-post-ip --netuid {config.network.netuid} "
            f"--subtensor.network {config.network.subtensor_network} "
            f"--external_port {config.api.api_port} "
            f"--wallet.name {config.wallet.wallet_name} "
            f"--wallet.hotkey {config.wallet.hotkey_name} "
            f"--external_ip <YOUR-IP>"
        )
        
        # Keep the loop alive
        while True:
            await asyncio.sleep(60)  # Check every minute
            
    except ValueError as e:
        logger.error("Miner startup aborted due to configuration error")
        return
    except Exception as e:
        logger.error(f"Error in miner background loop: {e}")
        return
