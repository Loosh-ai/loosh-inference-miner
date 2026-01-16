# Miner Quickstart Guide

Complete guide for setting up and running a miner on the Loosh Inference Subnet with supported hardware configurations and backend options.

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Installation](#installation)
- [Backend Configuration](#backend-configuration)
  - [vLLM (Recommended for Production)](#vllm-recommended-for-production)
  - [Ollama (Easy Setup)](#ollama-easy-setup)
  - [llama.cpp (CPU/Low-Resource)](#llamacpp-cpulow-resource)
- [Running the Miner](#running-the-miner)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Hardware Requirements

### Production Configurations

| GPU Tier | Model | Backend | System RAM | GPU | VRAM | Disk Space | Notes |
|----------|-------|---------|------------|-----|------|------------|-------|
| High-End | Qwen2.5-72B-Instruct-AWQ | vLLM | 128GB+ | 2x A100 80GB | 160GB | 500GB+ | Best performance |
| Mid-Range | Qwen2.5-14B-Instruct | vLLM | 64GB+ | 1x A100 80GB | 80GB | 200GB+ | Recommended |
| Entry | Qwen2.5-7B-Instruct-AWQ | vLLM | 32GB+ | 1x A10 24GB | 24GB | 100GB+ | Minimum viable |
| CPU Only | Qwen2.5-7B-Instruct-GGUF | llama.cpp | 64GB+ | None | N/A | 50GB+ | CPU inference |

See [min_compute.yml](min_compute.yml) for detailed hardware specifications and model recommendations.

## Installation

### 1. Prerequisites

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv

# Verify installation
uv --version
```

### 2. Clone Repository

```bash
git clone https://github.com/loosh-ai/loosh-inference-miner.git
cd loosh-inference-miner
```

### 3. Install Dependencies

Choose your backend and install corresponding dependencies:

```bash
# For vLLM (GPU required)
uv sync --extra vllm

# For Ollama (requires Ollama to be installed separately)
uv sync --extra ollama

# For llama.cpp (CPU or GPU)
uv sync --extra llamacpp

# For all backends
uv sync --extra all
```

### 4. Activate Virtual Environment

```bash
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

## Backend Configuration

### vLLM (Recommended for Production)

vLLM provides the best performance for GPU-based inference with automatic model downloading from HuggingFace.

#### Configuration

Create `.env` file:

```bash
cp env.example .env
```

Edit `.env`:

```bash
# Network (use finney for mainnet, test for testnet)
NETUID=78
SUBTENSOR_NETWORK=finney
SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443

# Wallet
WALLET_NAME=miner
HOTKEY_NAME=miner

# API
API_HOST=0.0.0.0
API_PORT=8000

# Backend
LLM_BACKEND=vllm
DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct

# vLLM Configuration
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=4096

# vLLM Advanced Options
VLLM_ENABLE_AUTO_TOOL_CHOICE=true
VLLM_TOOL_CALL_PARSER=hermes
VLLM_ENABLE_PREFIX_CACHING=true
VLLM_MAX_NUM_SEQS=64
VLLM_MAX_NUM_BATCHED_TOKENS=32768

# HuggingFace Cache (optional - use if you need more disk space)
# HUGGINGFACE_HUB_CACHE=/mnt/large-disk/huggingface-cache
```

#### Running vLLM Backend

The `run-miner.sh` script automatically starts vLLM and the miner:

```bash
./run-miner.sh
```

**What happens:**
1. Script checks if vLLM server is already running
2. If not, starts vLLM server with your configured model
3. Downloads model from HuggingFace (if first time) - progress bars shown
4. Waits for vLLM to be ready
5. Starts the miner API server

**Manual vLLM startup (optional):**

```bash
# Start vLLM server manually
.venv/bin/python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-14B-Instruct \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.9 \
  --max-model-len 4096 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --enable-prefix-caching \
  --max-num-seqs 64 \
  --max-num-batched-tokens 32768 \
  --port 8000

# In another terminal, start the miner
PYTHONPATH=. uv run uvicorn miner.miner_server:app --host 0.0.0.0 --port 8100
```

### Ollama (Easy Setup)

Ollama provides easy model management with a simple CLI.

#### Installation

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull qwen2.5:14b
```

#### Configuration

Edit `.env`:

```bash
LLM_BACKEND=ollama
DEFAULT_MODEL=qwen2.5:14b
OLLAMA_BASE_URL=http://localhost:11434
```

#### Running Ollama Backend

```bash
# Start Ollama server (if not already running)
ollama serve &

# Start miner
./run-miner.sh
```

### llama.cpp (CPU/Low-Resource)

llama.cpp works on CPU and GPU with GGUF format models.

#### Download GGUF Model

```bash
# Download a GGUF model
# Example: Qwen2.5-7B-Instruct Q4_K_M quantization
mkdir -p models
cd models
wget https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf
cd ..
```

#### Configuration

Edit `.env`:

```bash
LLM_BACKEND=llamacpp
MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m.gguf
```

#### Running llama.cpp Backend

```bash
# llama.cpp runs in-process, just start the miner
./run-miner.sh
```

## Running the Miner

### Using run-miner.sh (Recommended)

The script handles backend startup automatically:

```bash
./run-miner.sh
```

### Using PM2 (Production Deployment)

PM2 provides process management with auto-restart and logging:

```bash
# Install PM2
npm install -g pm2

# Start miner (automatically handles backend based on LLM_BACKEND)
pm2 start PM2/ecosystem.config.js

# View status
pm2 status

# View logs
pm2 logs loosh-inference-miner
pm2 logs loosh-vllm-server  # If using vLLM backend

# Stop
pm2 stop loosh-inference-miner

# Restart
pm2 restart loosh-inference-miner
```

### Manual Startup

```bash
# Activate virtual environment
source .venv/bin/activate

# Start miner API server
PYTHONPATH=. uvicorn miner.miner_server:app --host 0.0.0.0 --port 8000
```

## Testing

### Test vLLM Server

```bash
# Check if vLLM is running
curl http://localhost:8000/v1/models

# Test inference
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-14B-Instruct",
    "messages": [
      {"role": "user", "content": "Say hello!"}
    ],
    "max_tokens": 50
  }'
```

### Test Miner API

```bash
# Check availability endpoint
curl http://localhost:8100/availability

# View API documentation
# Open browser to: http://localhost:8100/docs
```

## Troubleshooting

### vLLM Issues

**Problem: "No module named 'vllm'"**
```bash
# Solution: Install vLLM dependencies
uv sync --extra vllm
```

**Problem: "Disk quota exceeded" during model download**
```bash
# Solution: Set custom cache location in .env
HUGGINGFACE_HUB_CACHE=/mnt/large-disk/huggingface-cache
```

**Problem: "hf_transfer not installed" warning**
```bash
# Solution: Install for faster downloads (optional)
pip install hf_transfer
# or
uv pip install hf_transfer
```

**Problem: No download progress shown**
```bash
# The script uses 'script' command to preserve TTY for progress bars
# If not working, check logs/vllm-server.log for progress
tail -f logs/vllm-server.log
```

### Ollama Issues

**Problem: "Connection refused" to Ollama**
```bash
# Solution: Start Ollama server
ollama serve

# Or check if it's running
ps aux | grep ollama
```

**Problem: Model not found**
```bash
# Solution: Pull the model first
ollama pull qwen2.5:14b

# List available models
ollama list
```

### General Issues

**Problem: Port already in use**
```bash
# Check what's using the port
lsof -i :8000

# Kill the process or use a different port
# Update API_PORT or VLLM_PORT in .env
```

**Problem: Out of memory**
```bash
# Solution: Reduce GPU memory utilization
GPU_MEMORY_UTILIZATION=0.8  # In .env

# Or use a smaller model
DEFAULT_MODEL=Qwen/Qwen2.5-7B-Instruct
```

**Problem: Git lock file error**
```bash
# Solution: Remove the lock file
rm -f .git/index.lock
```

## Performance Tuning

### vLLM Optimization

```bash
# For high-throughput scenarios
VLLM_MAX_NUM_SEQS=128
VLLM_MAX_NUM_BATCHED_TOKENS=65536

# For lower latency
VLLM_MAX_NUM_SEQS=32
VLLM_MAX_NUM_BATCHED_TOKENS=16384

# Disable features if not needed
VLLM_ENABLE_PREFIX_CACHING=false
VLLM_ENABLE_AUTO_TOOL_CHOICE=false
```

## Additional Resources

- **Full Documentation**: [README.md](README.md)
- **Hardware Specs**: [min_compute.yml](min_compute.yml)
- **Backend Details**: [miner/core/llms/README.md](miner/core/llms/README.md)
- **Docker Deployment**: See `docker/` directory
- **Testnet Guide**: [TESTNET.md](TESTNET.md) (if available)

## Support

- GitHub Issues: https://github.com/loosh-ai/loosh-inference-miner/issues
- Documentation: See README.md for detailed configuration options

