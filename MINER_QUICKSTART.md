# Miner Quickstart Guide

Quick reference for setting up a miner on the Loosh Inference Subnet with supported hardware configurations.

## Hardware Requirements

| Workload | Model | Backend | Memory | Processor | GPU | VRAM | Disk |
|----------|-------|---------|--------|-----------|-----|------|------|
| Miner | DeepSeek-V3 | vLLM | 256GB+ | 16+ cores | 8x B200 | 192GB | 2TB+ |
| Miner | DeepSeek-R1-Distill-Qwen-14B | vLLM | 64GB+ | 8+ cores | 1x A100 | 80GB | 500GB+ |

## Quick Setup

### 1. Clone & Install

```bash
git clone https://github.com/loosh-ai/loosh-inference-subnet.git
cd loosh-inference-subnet

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv

# Install dependencies (automatically creates virtual environment)
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### 2. Configure Environment

Create `miner/.env`:

```env
NETUID=21
SUBTENSOR_NETWORK=finney
SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443
WALLET_NAME=miner
HOTKEY_NAME=miner
API_HOST=0.0.0.0
API_PORT=8000
DEFAULT_MODEL=deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=4096
LOG_LEVEL=INFO
```

### 3. Start Miner

```bash
cd miner
python main.py
```

## Notes

- **VRAM**: Ensure your GPU has sufficient VRAM for the model size
- **Memory**: System RAM should be at least 64GB for optimal performance
- **Network**: Stable internet connection required for Bittensor communication
- **Wallet**: Ensure your Bittensor wallet is properly configured with sufficient stake

## Additional Resources

- See [README.md](README.md) for full project documentation
- See [TESTNET.md](TESTNET.md) for testnet deployment instructions

