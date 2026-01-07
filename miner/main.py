import os
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from miner.config.config import Config
from miner.dependencies import get_config
from miner.endpoints.inference import router as inference_router
from miner.endpoints.availability import router as availability_router

from miner.config.shared_config import get_miner_config

# MINER: MAIN LOOP [

from miner.network.InferenceSynapse import InferenceSynapse
from miner.network.bittensor_node import LooshCell, BittensorNode, create_node

import bittensor as bt

from miner.network.bittensor_node import ChallengeTask

async def main_loop():
    """Main function to run the bittensor node."""
    try:
        config = get_miner_config()
    except ValueError as e:
        # Configuration error already logged with helpful message
        logger.error("Miner startup aborted due to configuration error")
        return
    except Exception as e:
        error_msg = (
            f"\n{'='*70}\n"
            f"CONFIGURATION ERROR: Failed to load miner configuration\n"
            f"{'='*70}\n"
            f"Error: {str(e)}\n"
            f"\nPlease check your environment variables or .env file.\n"
            f"See environments/env.miner.example for valid configuration options.\n"
            f"{'='*70}\n"
        )
        logger.error(error_msg)
        return

    config.netuid = config.network.netuid
    config.subtensor_network = config.network.subtensor_network
    config.wallet_name = config.wallet.wallet_name
    config.hotkey_name = config.wallet.hotkey_name

    try:
        node = create_node(config)
    except Exception as e:
        error_msg = str(e)
        if "Wallet" in error_msg or "wallet" in error_msg or "keypair" in error_msg or "No such file" in error_msg:
            logger.error(
                f"\n{'='*70}\n"
                f"MINER STARTUP FAILED: Wallet not found\n"
                f"{'='*70}\n"
                f"The miner requires a valid Bittensor wallet to start.\n"
                f"\nWallet: {config.wallet_name}\n"
                f"Hotkey: {config.hotkey_name}\n"
                f"\nTo create the wallet, run:\n"
                f"  docker exec -it loosh-inference-subnet-miner btcli wallet new_coldkey \\\n"
                f"    --wallet.name {config.wallet_name} \\\n"
                f"    --wallet.path /root/.bittensor/wallets \\\n"
                f"    --no-use-password --n_words 24\n"
                f"\n  docker exec -it loosh-inference-subnet-miner btcli wallet new_hotkey \\\n"
                f"    --wallet.name {config.wallet_name} \\\n"
                f"    --wallet.path /root/.bittensor/wallets \\\n"
                f"    --hotkey {config.hotkey_name} \\\n"
                f"    --no-use-password --n_words 24\n"
                f"\nThen restart the container:\n"
                f"  docker compose restart miner\n"
                f"{'='*70}\n"
            )
            # Don't raise - allow the API to continue running
            return
        else:
            logger.error(f"Failed to create Bittensor node: {error_msg}")
            raise

    try:
        # STAGE A - Use configured axon port (default: 8089, set via AXON_PORT env var)
        try:
            node.stageA(port=config.axon_port)
        except Exception as e:
            error_msg = str(e)
            if "subtensor" in error_msg.lower() or "network" in error_msg.lower() or "connection" in error_msg.lower():
                logger.error(
                    f"\n{'='*70}\n"
                    f"NETWORK ERROR: Failed to connect to Bittensor network\n"
                    f"{'='*70}\n"
                    f"Network: {config.subtensor_network}\n"
                    f"Address: {config.subtensor_address}\n"
                    f"Error: {error_msg}\n"
                    f"\nThis is usually caused by:\n"
                    f"  - Network connectivity issues\n"
                    f"  - Invalid SUBTENSOR_ADDRESS\n"
                    f"  - Network endpoint is down or unreachable\n"
                    f"\nPlease check:\n"
                    f"  - SUBTENSOR_NETWORK environment variable\n"
                    f"  - SUBTENSOR_ADDRESS environment variable\n"
                    f"  - Network connectivity to the Bittensor network\n"
                    f"{'='*70}\n"
                )
                # Don't raise - allow the API to continue running
                return
            else:
                raise

        node.stage3()

        axon = node.axon
        dendrite = node.dendrite

        synapse = bt.Synapse(
            # Add inputs depending on the subnet's expected Synapse fields
        )

        response = await dendrite.forward(
            axons=[axon],
            synapse=synapse,
            timeout=10.0,  # seconds
        )

        print(response)

        synapse = InferenceSynapse(prompt='prompt', model='model', max_tokens=100, temperature=0.5, top_p=0.9, completion="")

        response = await dendrite.forward(
            axons=[axon],
            synapse=synapse,
            timeout=360.0,  # seconds
        )

        print(response)


#        synapse = ChallengeTask(prompt='prompt')
#
#        response = await dendrite.forward(
#            axons=[axon],
#            synapse=synapse,
#            timeout=10.0,  # seconds
#        )

#        response = dendrite.query(axon, ["ping"])
#        print(response)


        # MAIN LOOP - UNLIMITED [

        # Keep running
        bt.logging.info("Bittensor node is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

        # MAIN LOOP - UNLIMITED ]
            
    except KeyboardInterrupt:
        bt.logging.info("Received interrupt signal")
    except FileNotFoundError as e:
        error_msg = str(e)
        if "Wallet" in error_msg or "wallet" in error_msg or "keypair" in error_msg:
            logger.error(
                f"\n{'='*70}\n"
                f"MINER STARTUP FAILED: Wallet not found\n"
                f"{'='*70}\n"
                f"The miner requires a valid Bittensor wallet to start.\n"
                f"\nWallet: {config.wallet_name}\n"
                f"Hotkey: {config.hotkey_name}\n"
                f"\nTo create the wallet, run:\n"
                f"  docker exec -it loosh-inference-subnet-miner btcli wallet new_coldkey \\\n"
                f"    --wallet.name {config.wallet_name} \\\n"
                f"    --wallet.path /root/.bittensor/wallets \\\n"
                f"    --no-use-password --n_words 24\n"
                f"\n  docker exec -it loosh-inference-subnet-miner btcli wallet new_hotkey \\\n"
                f"    --wallet.name {config.wallet_name} \\\n"
                f"    --wallet.path /root/.bittensor/wallets \\\n"
                f"    --hotkey {config.hotkey_name} \\\n"
                f"    --no-use-password --n_words 24\n"
                f"\nThen restart the container:\n"
                f"  docker compose restart miner\n"
                f"{'='*70}\n"
            )
            # Don't raise - allow the API to continue running
            return
        else:
            raise
    except Exception as e:
        error_msg = str(e)
        if "Failed to load keys" in error_msg or "keypair" in error_msg:
            logger.error(
                f"\n{'='*70}\n"
                f"MINER STARTUP FAILED: Wallet error\n"
                f"{'='*70}\n"
                f"Error: {error_msg}\n"
                f"\nPlease ensure wallet files are properly configured.\n"
                f"Wallet: {config.wallet_name}, Hotkey: {config.hotkey_name}\n"
                f"{'='*70}\n"
            )
            # Don't raise - allow the API to continue running
            return
        else:
            bt.logging.error(f"Error in main loop: {str(e)}")
            raise
    finally:
        if 'node' in locals():
            try:
                node.stop()
                bt.logging.info("Bittensor node stopped")
            except:
                pass


# MINER: MAIN LOOP ]

def get_config():
    return ValidatorConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    main_loop_task = asyncio.create_task(main_loop())
    yield
    # Shutdown
    main_loop_task.cancel()
    try:
        await main_loop_task
    except asyncio.CancelledError:
        pass

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Add dependencies
app.dependency_overrides[Config] = get_config

# API

# Include routers with their prefixes and tags
app.include_router(
    inference_router,
    prefix="/inference",
    tags=["inference"]
)
app.include_router(
    availability_router,
    prefix="/availability",
    tags=["availability"]
)
