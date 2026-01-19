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
# Note: vLLM exposes an OpenAI-compatible API but does NOT require OpenAI models
# You can use any model compatible with vLLM (HuggingFace, local, etc.)
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

## Inference Server Setup

### Understanding the Architecture

The Loosh miner uses a **two-process architecture**:

1. **Inference Server** - Runs the LLM model and handles inference requests (e.g., vLLM, Ollama, llama.cpp server)
2. **Miner API Server** - FastAPI application that receives challenges, calls the inference server, and returns responses

```
Validator → [Miner API Server] → [Inference Server (with LLM)] → Response
```

### Default Configuration: vLLM

**This repository is pre-configured to run a vLLM inference server by default** when using:
- `run-miner.sh` script
- PM2 deployment (`PM2/ecosystem.config.js`)

#### What Happens Automatically

When you run `./run-miner.sh` or `pm2 start PM2/ecosystem.config.js` with `LLM_BACKEND=vllm`:

1. **vLLM Server Process** is started automatically:
   - Reads configuration from `.env` file
   - Starts `python -m vllm.entrypoints.openai.api_server`
   - Downloads model from HuggingFace if not cached
   - Exposes OpenAI-compatible API on `VLLM_PORT` (default: 8000)
   - Applies all vLLM settings (tensor parallelism, GPU memory, context length, etc.)

2. **Miner API Process** is started:
   - Waits for vLLM server to be ready
   - Connects to vLLM at `VLLM_API_BASE` (default: http://localhost:8000/v1)
   - Starts FastAPI server on `API_PORT` (default: 8100)

#### vLLM Configuration in .env

The following environment variables control the vLLM inference server:

```bash
# Backend selection - determines which inference server to use
LLM_BACKEND=vllm

# Model to load in vLLM
DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct

# vLLM server URL (where vLLM will listen)
VLLM_API_BASE=http://localhost:8000/v1
VLLM_PORT=8000

# GPU configuration (passed to vLLM server)
TENSOR_PARALLEL_SIZE=1              # Number of GPUs for tensor parallelism
GPU_MEMORY_UTILIZATION=0.9          # Fraction of GPU memory to use
MAX_MODEL_LEN=4096                  # Maximum context length

# Advanced vLLM features
VLLM_ENABLE_AUTO_TOOL_CHOICE=true   # Enable automatic tool calling
VLLM_TOOL_CALL_PARSER=hermes        # Tool call parser (hermes, functionary, mistral)
VLLM_ENABLE_PREFIX_CACHING=true     # Cache common prompt prefixes
VLLM_MAX_NUM_SEQS=64                # Max parallel sequences
VLLM_MAX_NUM_BATCHED_TOKENS=32768   # Max tokens in a batch

# Model cache location (optional)
# HUGGINGFACE_HUB_CACHE=/mnt/large-disk/huggingface-cache
```

### Using a Different Inference Server

If you want to use **Ollama** or **llama.cpp** instead of vLLM, you need to configure the system differently:

#### Option 1: Ollama (Managed Separately)

Ollama runs as a **separate system service** - it's NOT automatically started by the miner scripts.

**Setup Steps:**

1. **Install Ollama** (one-time setup):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull your model**:
   ```bash
   ollama pull qwen2.5:14b
   ```

3. **Start Ollama server** (must be running before miner):
   ```bash
   ollama serve
   # Or run as system service (Linux):
   systemctl enable ollama
   systemctl start ollama
   ```

4. **Configure miner** in `.env`:
   ```bash
   LLM_BACKEND=ollama
   DEFAULT_MODEL=qwen2.5:14b
   OLLAMA_BASE_URL=http://localhost:11434
   ```

5. **Start miner** (Ollama must already be running):
   ```bash
   ./run-miner.sh
   # or
   pm2 start PM2/ecosystem.config.js
   ```

**Important:** Unlike vLLM, the `run-miner.sh` script and PM2 config **do NOT start Ollama** for you. You must start `ollama serve` separately before running the miner.

#### Option 2: llama.cpp (In-Process or Server)

llama.cpp can run in two modes:

**Mode A: In-Process (No Separate Server)**

llama.cpp loads the model directly in the miner process:

1. **Download a GGUF model**:
   ```bash
   mkdir -p models
   wget https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf -P models/
   ```

2. **Configure** in `.env`:
   ```bash
   LLM_BACKEND=llamacpp
   MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m.gguf
   ```

3. **Start miner** (no separate server needed):
   ```bash
   ./run-miner.sh
   ```

**Mode B: llama.cpp Server (Separate Process)**

If you want to run llama.cpp as a separate OpenAI-compatible server:

1. **Start llama.cpp server manually**:
   ```bash
   python -m llama_cpp.server --model ./models/qwen2.5-7b-instruct-q4_k_m.gguf --port 8080
   ```

2. **Configure miner** to connect to it:
   ```bash
   LLM_BACKEND=llamacpp
   # Set the server URL if running separately
   # (This requires modifying config to add llamacpp_api_base support)
   ```

**Note:** The default llama.cpp integration runs in-process. If you need server mode, you'll need to modify the configuration.

### Custom Inference Servers

Want to use **TGI (Text Generation Inference)**, **LocalAI**, or another OpenAI-compatible server?

#### Requirements

Your inference server must:
1. Expose an **OpenAI-compatible Chat Completions API** endpoint
2. Accept requests at `/v1/chat/completions`
3. Support the standard message format and response structure

#### Setup Steps

1. **Start your custom inference server** on a specific port (e.g., 8000)

2. **Configure via environment variables** - No code editing required!

   Since your custom server is OpenAI-compatible, you can use the vLLM backend configuration to point to it:
   
   ```bash
   # In your .env file
   LLM_BACKEND=vllm
   VLLM_API_BASE=http://localhost:8000/v1  # Your custom server URL
   DEFAULT_MODEL=your-model-name
   ```

3. **Disable automatic vLLM startup**:
   - Don't use `run-miner.sh` (it will try to start vLLM)
   - Instead, start only the miner API:
     ```bash
     source .venv/bin/activate
     PYTHONPATH=. uvicorn miner.miner_server:app --host 0.0.0.0 --port 8100
     ```

**Advanced:** If you need more control or want to create a custom backend class, see `miner/core/llms/README.md` for backend development guidelines. But for most OpenAI-compatible servers, just pointing `VLLM_API_BASE` to your server is sufficient.

### Summary: What You Need to Know

| Backend | Auto-Started by Scripts? | Separate Server Required? | Configuration |
|---------|-------------------------|---------------------------|---------------|
| **vLLM** | ✅ Yes (default) | No | Set `LLM_BACKEND=vllm` in `.env` |
| **Ollama** | ❌ No | Yes - start `ollama serve` first | Set `LLM_BACKEND=ollama` in `.env` |
| **llama.cpp** | ❌ No (in-process) | No (runs in miner process) | Set `LLM_BACKEND=llamacpp` in `.env` |
| **Custom** | ❌ No | Yes - start your server first | Configure URL + model name |

**Key Point:** The repository is optimized for vLLM by default. If you choose a different backend, you're responsible for starting and managing that inference server separately.

## Running the Miner

### Using run-miner.sh (Recommended)

The script handles backend startup automatically (vLLM only):

```bash
./run-miner.sh
```

### Using PM2 (Production Deployment)

PM2 provides process management with auto-restart and logging.

**Note:** PM2 will automatically start the vLLM server if `LLM_BACKEND=vllm`. For other backends (Ollama, llama.cpp), you must start them separately before running PM2.

```bash
# Install PM2
npm install -g pm2

# Start miner (automatically handles vLLM backend startup)
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

**For Ollama users:** Start `ollama serve` before running `pm2 start`.

**For llama.cpp users:** llama.cpp runs in-process with the miner, no separate server needed.

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

