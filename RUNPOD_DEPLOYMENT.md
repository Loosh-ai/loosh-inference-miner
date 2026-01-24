# Loosh Inference Miner - RunPod Deployment Guide

Complete guide for deploying the Loosh Inference Miner on RunPod with GPU acceleration.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Part 1: Build Docker Image](#part-1-build-docker-image)
- [Part 2: Setup RunPod Network Volume](#part-2-setup-runpod-network-volume)
- [Part 3: Upload Wallet Files](#part-3-upload-wallet-files)
- [Part 4: Configure Environment](#part-4-configure-environment)
- [Part 5: Deploy Miner Pod](#part-5-deploy-miner-pod)
- [Part 6: Verify and Monitor](#part-6-verify-and-monitor)
- [Troubleshooting](#troubleshooting)
- [Cost Optimization](#cost-optimization)

## Overview

RunPod provides GPU infrastructure ideal for running LLM inference miners. This guide covers:
- Building a RunPod-optimized Docker image
- Managing persistent storage with network volumes
- Securely handling Bittensor wallet files
- Deploying and monitoring your miner

### Architecture

**Standard Miner (llamacpp/ollama):**
```
RunPod Pod
├── Miner Container (single process)
│   ├── FastAPI Server (port 8000)
│   ├── Fiber MLTS encryption
│   └── LLM Backend (llamacpp/ollama via external API)
├── Network Volume (mounted at /workspace)
│   ├── .env (configuration)
│   ├── .bittensor/wallets/ (your keys)
│   └── models/ (cached models)
└── GPU (NVIDIA A100/H100/etc.)
```

**Unified vLLM Miner (recommended for RunPod):**
```
RunPod Pod
├── Miner Container (unified multi-process)
│   ├── supervisord (process manager)
│   │   ├── vLLM Server (127.0.0.1:8001, internal only)
│   │   └── Miner API (0.0.0.0:8000, external)
│   ├── Fiber MLTS encryption
│   └── GPU-accelerated inference
├── Network Volume (mounted at /workspace)
│   ├── .env (configuration)
│   ├── .bittensor/wallets/ (your keys)
│   └── models/ (cached HuggingFace models)
└── GPU (NVIDIA A100/H100/etc.)
```

## Prerequisites

### Local Machine

- Docker installed
- Git
- SSH client
- Your Bittensor wallet files (coldkey + hotkey)

### RunPod Account

- RunPod account with credits
- Basic familiarity with RunPod dashboard
- Recommended: $50-100 initial credits for testing

### Bittensor Setup

- Registered on subnet (NETUID 78 for mainnet)
- Wallet with sufficient TAO for registration
- Knowledge of your wallet name and hotkey name

## Part 1: Build Docker Image

### Step 1.1: Clone Repository

```bash
git clone https://github.com/Loosh-ai/loosh-inference-miner.git
cd loosh-inference-miner
```

### Step 1.2: Choose Your Deployment Type

The miner supports two deployment types:

#### Option A: Unified vLLM (Recommended for RunPod)
**All-in-one container with miner + vLLM server managed by supervisord**

**Advantages:**
- Single container deployment
- No external LLM API needed
- GPU-optimized inference with vLLM
- Automatic process management
- Lower latency (internal communication)

**Disadvantages:**
- Larger image size (~15GB)
- Requires GPU with sufficient VRAM
- More complex process management

#### Option B: Standard Miner (llamacpp/ollama)
**Miner only, connects to external LLM API**

**Advantages:**
- Smaller image size (~3-4GB)
- Flexible LLM backend (use any OpenAI-compatible API)
- Can use external vLLM/Ollama service

**Disadvantages:**
- Requires separate LLM service
- Network latency for API calls
- More complex infrastructure

### Step 1.3: Build the Image

#### For Unified vLLM (Recommended):

```bash
# Build with CUDA base and vLLM support (unified miner+vLLM)
docker build \
  --build-arg BUILD_ENV=cuda \
  --build-arg OPTIONAL_DEPS=vllm \
  --build-arg VENV_NAME=.venv-docker \
  --target final-vllm \
  -f docker/Dockerfile \
  -t loosh-miner:runpod-vllm \
  .
```

#### For Standard Miner (llamacpp):

```bash
# Build with CUDA base and llamacpp
docker build \
  --build-arg BUILD_ENV=cuda \
  --build-arg OPTIONAL_DEPS=llamacpp \
  --build-arg VENV_NAME=.venv-docker \
  --target final-single \
  -f docker/Dockerfile \
  -t loosh-miner:runpod \
  .
```

**Build Arguments Explained:**
- `BUILD_ENV=cuda` - Uses NVIDIA CUDA base image (nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04)
  - **Not** using RunPod's bloated PyTorch base (saves ~9GB)
  - Provides CUDA runtime + cuDNN for GPU acceleration
- `OPTIONAL_DEPS=vllm` or `llamacpp` - Installs specific backend dependencies
- `VENV_NAME=.venv-docker` - Custom venv name for Docker environment
- `--target final-vllm` - Builds unified multi-process image with supervisord
- `--target final-single` - Builds single-process miner only

**Why Not `BUILD_ENV=runpod`?**
- The RunPod PyTorch base image is ~15GB (includes pre-installed PyTorch, Jupyter, etc.)
- Using `cuda` base provides CUDA runtime without the bloat
- **Expected image sizes:**
  - **Base miner (llamacpp)**: ~6-7GB total (CUDA runtime + Python + base deps)
  - **vLLM unified**: ~13-16GB total (CUDA runtime + vLLM + PyTorch + ML libraries)
- The vLLM stack (vLLM + PyTorch + Triton + xformers) adds ~8-10GB of dependencies
- This is unavoidable - vLLM requires these large ML libraries for GPU inference

### Step 1.4: Test Image Locally (Optional)

#### Test Unified vLLM Image:

```bash
# Quick test
docker run --rm loosh-miner:runpod-vllm python --version

# Test with environment (requires GPU)
docker run --rm --gpus all \
  -e NETUID=78 \
  -e SUBTENSOR_NETWORK=finney \
  -e LLM_BACKEND=vllm \
  -e DEFAULT_MODEL=mistralai/Mistral-7B-Instruct-v0.2 \
  -p 8000:8000 \
  loosh-miner:runpod-vllm

# In another terminal, check if both processes are running
docker exec <container_id> supervisorctl status
# Should show:
# miner                            RUNNING   pid 123, uptime 0:00:10
# vllm                             RUNNING   pid 122, uptime 0:00:10
```

#### Test Standard Miner Image:

```bash
# Quick test
docker run --rm loosh-miner:runpod python --version

# Test with environment
docker run --rm \
  -e NETUID=78 \
  -e SUBTENSOR_NETWORK=finney \
  loosh-miner:runpod uv run python -c "from miner.config.config import MinerConfig; print(MinerConfig())"
```

### Step 1.5: Push to Docker Registry

RunPod can pull from Docker Hub, GitHub Container Registry, or private registries.

#### For Unified vLLM Image:

**Option A: Docker Hub**

```bash
# Tag for Docker Hub
docker tag loosh-miner:runpod-vllm yourusername/loosh-miner:runpod-vllm

# Login and push
docker login
docker push yourusername/loosh-miner:runpod-vllm
```

**Option B: GitHub Container Registry**

```bash
# Tag for GHCR
docker tag loosh-miner:runpod-vllm ghcr.io/yourusername/loosh-miner:runpod-vllm

# Login and push
echo $GITHUB_TOKEN | docker login ghcr.io -u yourusername --password-stdin
docker push ghcr.io/yourusername/loosh-miner:runpod-vllm
```

**Option C: Use Pre-built Image**

If available, use the official unified image:
```bash
looshcontainers-hbefcrffb7fnecbn.azurecr.io/loosh-inference-miner-runpod-vllm:production
```

#### For Standard Miner Image:

Follow the same pattern but use `loosh-miner:runpod` or the official image:
```bash
looshcontainers-hbefcrffb7fnecbn.azurecr.io/loosh-inference-miner-runpod:production
```

## Part 2: Setup RunPod Network Volume

### Step 2.1: Create Network Volume

1. **Go to RunPod Dashboard** → **Storage** → **Network Volumes**
2. **Click "New Network Volume"**
3. **Configure:**
   - Name: `loosh-miner-storage`
   - Size: 50 GB (minimum) - 100 GB recommended for model caching
   - Region: Choose same region as your pods for best performance
4. **Click "Create"**
5. **Note the Volume ID** - you'll need this later

### Step 2.2: Create Temporary Pod for Setup

You need a temporary pod to upload files to the volume.

1. **Go to** **Pods** → **Deploy**
2. **Select template:** "RunPod Pytorch" or "Ubuntu with SSH"
3. **Configure:**
   - GPU: Any cheap option (1x RTX 3070 is fine for setup)
   - Volume: Attach your `loosh-miner-storage` volume at `/workspace`
   - SSH: Enable public key or password authentication
4. **Deploy pod**
5. **Wait for pod to be ready** (status: RUNNING)
6. **Note the SSH connection string** (e.g., `ssh root@<pod-id>.ssh.runpod.io -p 12345`)

## Part 3: Upload Wallet Files

### Step 3.1: Locate Your Wallet Files

On your local machine:

```bash
# Find your wallet
ls -la ~/.bittensor/wallets/

# Structure should be:
~/.bittensor/wallets/
└── miner/              # Your wallet name
    ├── coldkey         # Main wallet key
    └── hotkeys/
        └── miner       # Your hotkey
```

### Step 3.2: Upload via SCP

**Option A: Upload Existing Wallets**

```bash
# Connect to your temporary pod (from Step 2.2)
# Replace with your actual SSH details from RunPod dashboard

# Create directory structure on volume
ssh root@<pod-id>.ssh.runpod.io -p <port> "mkdir -p /workspace/.bittensor/wallets/miner/hotkeys"

# Upload coldkey
scp -P <port> ~/.bittensor/wallets/miner/coldkey root@<pod-id>.ssh.runpod.io:/workspace/.bittensor/wallets/miner/

# Upload hotkey
scp -P <port> ~/.bittensor/wallets/miner/hotkeys/miner root@<pod-id>.ssh.runpod.io:/workspace/.bittensor/wallets/miner/hotkeys/

# Verify upload
ssh root@<pod-id>.ssh.runpod.io -p <port> "ls -la /workspace/.bittensor/wallets/miner/"
```

**Option B: Create New Wallets in Pod**

```bash
# SSH into temporary pod
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Install btcli if not available
pip install bittensor

# Create directory
mkdir -p /workspace/.bittensor/wallets

# Create new coldkey
btcli wallet new_coldkey \
  --wallet.name miner \
  --wallet.path /workspace/.bittensor/wallets \
  --no-use-password \
  --n_words 24

# IMPORTANT: Save your seed phrase securely!

# Create hotkey
btcli wallet new_hotkey \
  --wallet.name miner \
  --wallet.path /workspace/.bittensor/wallets \
  --hotkey miner \
  --no-use-password \
  --n_words 24

# IMPORTANT: Save your hotkey seed phrase securely!

# Verify
ls -la /workspace/.bittensor/wallets/miner/
```

### Step 3.3: Set Proper Permissions

```bash
# SSH into temporary pod
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Set restrictive permissions
chmod 600 /workspace/.bittensor/wallets/miner/coldkey
chmod 600 /workspace/.bittensor/wallets/miner/hotkeys/miner
chmod 700 /workspace/.bittensor/wallets/miner/hotkeys
chmod 700 /workspace/.bittensor/wallets/miner

# Verify
ls -la /workspace/.bittensor/wallets/miner/
ls -la /workspace/.bittensor/wallets/miner/hotkeys/
```

## Part 4: Configure Environment

### Step 4.1: Create .env File on Volume

SSH into your temporary pod and create the configuration file:

#### For Unified vLLM (Recommended):

```bash
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Create .env file for unified vLLM deployment
cat > /workspace/.env << 'EOF'
# =============================================================================
# Loosh Inference Miner - Unified vLLM Configuration for RunPod
# =============================================================================

# =============================================================================
# Network Configuration - MAINNET
# =============================================================================
NETUID=78
SUBTENSOR_NETWORK=finney
SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443

# Network Configuration - TESTNET (uncomment to use)
#NETUID=78
#SUBTENSOR_NETWORK=test
#SUBTENSOR_ADDRESS=wss://test.finney.opentensor.ai:443

# =============================================================================
# Wallet Configuration
# =============================================================================
# Must match your wallet directory structure
WALLET_NAME=miner
HOTKEY_NAME=miner

# =============================================================================
# API Configuration
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8000

# Axon port for Bittensor network communication
AXON_PORT=8089

# =============================================================================
# LLM Backend Configuration - UNIFIED vLLM
# =============================================================================
# Backend: vllm (unified - runs internally via supervisord)
LLM_BACKEND=vllm

# vLLM internal API endpoint (managed by supervisord, port 8001 internal)
VLLM_API_BASE=http://127.0.0.1:8001/v1

# Model Selection - Choose based on your GPU
# For A100 80GB: Qwen/Qwen2.5-72B-Instruct-AWQ
# For A100 40GB: Qwen/Qwen2.5-32B-Instruct
# For A10 24GB: Qwen/Qwen2.5-14B-Instruct
# For RTX 5080 16GB: Qwen/Qwen2.5-7B-Instruct
DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct

DEFAULT_MAX_TOKENS=5120
DEFAULT_TEMPERATURE=0.7
DEFAULT_TOP_P=0.95

# =============================================================================
# GPU Configuration
# =============================================================================
# Number of GPUs for tensor parallelism
TENSOR_PARALLEL_SIZE=1

# GPU memory utilization (0.0 to 1.0)
# 0.9 = use 90% of GPU memory, leave 10% for system
GPU_MEMORY_UTILIZATION=0.9

# Maximum context length
# Adjust based on your GPU VRAM
MAX_MODEL_LEN=10240

# =============================================================================
# vLLM Advanced Configuration
# =============================================================================
VLLM_ENABLE_AUTO_TOOL_CHOICE=true
VLLM_TOOL_CALL_PARSER=hermes
VLLM_ENABLE_PREFIX_CACHING=true
VLLM_MAX_NUM_SEQS=64
VLLM_MAX_NUM_BATCHED_TOKENS=32768

# =============================================================================
# HuggingFace Cache Configuration
# =============================================================================
# Store models on the network volume for persistence
HUGGINGFACE_HUB_CACHE=/workspace/models/huggingface
HF_HOME=/workspace/models

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL=INFO

# =============================================================================
# Fiber MLTS Configuration
# =============================================================================
FIBER_KEY_TTL_SECONDS=3600
FIBER_HANDSHAKE_TIMEOUT_SECONDS=30
FIBER_ENABLE_KEY_ROTATION=true

# =============================================================================
# Concurrency Configuration
# =============================================================================
MAX_CONCURRENT_REQUESTS=10

# =============================================================================
# RunPod Specific
# =============================================================================
# Optional: Set if you need specific port configurations
# RUNPOD_POD_ID will be set automatically by RunPod
EOF

# Create model cache directories
mkdir -p /workspace/models/huggingface
mkdir -p /workspace/logs

# Verify
cat /workspace/.env
```

### Step 4.2: GPU-Specific Configurations

Adjust your `.env` based on the GPU you'll use:

#### **For A100 80GB:**
```bash
DEFAULT_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.95
MAX_MODEL_LEN=32768
```

#### **For A100 40GB:**
```bash
DEFAULT_MODEL=Qwen/Qwen2.5-32B-Instruct
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=16384
```

#### **For A10 24GB:**
```bash
DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=8192
```

#### **For RTX 5080 16GB:**
```bash
DEFAULT_MODEL=Qwen/Qwen2.5-7B-Instruct
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.85
MAX_MODEL_LEN=4096
```

### Step 4.3: Stop Temporary Pod

Once files are uploaded and configured:

1. **Go to RunPod Dashboard** → **My Pods**
2. **Stop** (not delete) the temporary pod
3. This saves your credits while keeping the volume data

## Part 5: Deploy Miner Pod

### Step 5.1: Deploy Production Pod

#### For Unified vLLM Deployment (Recommended):

1. **Go to** **Pods** → **Deploy**

2. **Select GPU:**
   - For production: A100 40GB or 80GB recommended
   - For testing: A10 24GB or RTX 3090
   - Consider spot instances for 50-70% cost savings

3. **Select your Docker image:**
   - Custom: `yourusername/loosh-miner:runpod-vllm`
   - Or official: `looshcontainers-hbefcrffb7fnecbn.azurecr.io/loosh-inference-miner-runpod-vllm:production`

4. **Configure Volume:**
   - Attach your `loosh-miner-storage` volume
   - Mount path: `/workspace`

5. **Configure Volume Mounts:**
   
   In "Docker Options" → "Volume Mounts":
   ```
   /workspace/.bittensor/wallets:/root/.bittensor/wallets:ro
   /workspace/.env:/app/.env:ro
   /workspace/models:/workspace/models
   /workspace/logs:/app/logs
   ```

6. **Configure Ports:**
   - Container Port: `8000` → HTTP (Miner API - external access)
   - Container Port: `8089` → HTTP (Axon - for Bittensor network)
   - **Note**: Port 8001 is internal only (vLLM) and not exposed

7. **Environment Variables (Optional - if not using .env):**
   
   **Important for unified vLLM:**
   ```
   LLM_BACKEND=vllm
   VLLM_API_BASE=http://127.0.0.1:8001/v1
   DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct
   NETUID=78
   SUBTENSOR_NETWORK=finney
   SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443
   WALLET_NAME=miner
   HOTKEY_NAME=miner
   ```

8. **Advanced Options:**
   - Enable SSH access (recommended for debugging)
   - Set GPU count (usually 1)
   - Set memory limits if needed

9. **Deploy!**

#### For Standard Miner Deployment:

Follow the same steps but:
- Use image: `loosh-inference-miner-runpod:production` (without vllm)
- Set `LLM_BACKEND=llamacpp` or point to external LLM API
- Only expose port 8000 and 8089

### Step 5.2: Verify Deployment

#### For Unified vLLM:

```bash
# SSH into the pod
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Check supervisord status (should show both miner and vllm running)
supervisorctl status

# Expected output:
# miner                            RUNNING   pid 123, uptime 0:05:00
# vllm                             RUNNING   pid 122, uptime 0:05:00

# Check vLLM is accessible internally
curl http://127.0.0.1:8001/v1/models

# Check miner API is working
curl http://localhost:8000/availability

# Check logs
supervisorctl tail -f miner
supervisorctl tail -f vllm
```

#### For Standard Miner:

```bash
# SSH into the pod
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Check miner process
ps aux | grep miner

# Check miner API
curl http://localhost:8000/availability
```
   - For testing: A10 24GB or RTX 3090
   - Consider spot instances for 50-70% cost savings

3. **Select your Docker image:**
   - Custom: `yourusername/loosh-miner:runpod`
   - Or official: `looshcontainers-hbefcrffb7fnecbn.azurecr.io/loosh-inference-miner:production`

4. **Configure Volume:**
   - Attach your `loosh-miner-storage` volume
   - Mount path: `/workspace`

5. **Configure Volume Mounts:**
   
   In "Docker Options" → "Volume Mounts":
   ```
   /workspace/.bittensor/wallets:/root/.bittensor/wallets:ro
   /workspace/.env:/app/.env:ro
   /workspace/models:/workspace/models
   /workspace/logs:/app/logs
   ```

6. **Configure Ports:**
   - Container Port: `8000` → HTTP
   - Container Port: `8089` → HTTP (for Axon)

7. **Environment Variables (Optional - if not using .env):**
   
   Only set these if you're NOT using the .env file:
   ```
   NETUID=78
   SUBTENSOR_NETWORK=finney
   SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443
   WALLET_NAME=miner
   HOTKEY_NAME=miner
   ```

8. **Advanced Options:**
   - Enable SSH access (recommended for debugging)
   - Set GPU count (usually 1)
   - Set memory limits if needed

9. **Deploy!**

### Step 5.2: Alternative - Docker Run Command

If you prefer command-line deployment, use RunPod's Docker override:

```bash
docker run -d \
  --name loosh-miner \
  --gpus all \
  -p 8000:8000 \
  -p 8089:8089 \
  -v /workspace/.bittensor/wallets:/root/.bittensor/wallets:ro \
  -v /workspace/.env:/app/.env:ro \
  -v /workspace/models:/workspace/models \
  -v /workspace/logs:/app/logs \
  yourusername/loosh-miner:runpod
```

## Part 6: Verify and Monitor

### Step 6.1: Check Pod Status

1. **Wait for pod to start** (status: RUNNING)
2. **Check logs** in RunPod dashboard
3. **Look for:**
   ```
   INFO: Started server process
   INFO: Waiting for application startup
   INFO: Application startup complete
   INFO: Uvicorn running on http://0.0.0.0:8000
   ```

### Step 6.2: Verify Wallet Access

SSH into your pod:

```bash
ssh root@<pod-id>.ssh.runpod.io -p <port>

# Check wallet files are mounted
ls -la /root/.bittensor/wallets/miner/

# Verify wallet with btcli
btcli wallet overview --wallet.name miner --wallet.hotkey miner --netuid 78

# Should show your wallet balance and registration status
```

### Step 6.3: Test Miner API

```bash
# From inside the pod or via HTTP endpoint

# Check health
curl http://localhost:8000/health

# Check availability
curl http://localhost:8000/availability

# View API docs
curl http://localhost:8000/docs
```

### Step 6.4: Check Subnet Registration

```bash
# Inside pod
btcli subnet list --netuid 78

# Check if your miner is registered
btcli wallet overview --netuid 78 --wallet.name miner --wallet.hotkey miner
```

### Step 6.5: Monitor Logs

```bash
# View live logs
ssh root@<pod-id>.ssh.runpod.io -p <port>
tail -f /app/logs/miner.log

# Or use RunPod dashboard logs viewer
```

### Step 6.6: Monitor GPU Usage

```bash
# Inside pod
watch -n 1 nvidia-smi

# Check GPU memory and utilization
```

## Troubleshooting

### Wallet Not Found

**Symptoms:**
```
FileNotFoundError: Wallet file not found at /root/.bittensor/wallets/miner/coldkey
```

**Solutions:**
```bash
# Verify volume is mounted
mount | grep workspace

# Check files exist
ls -la /workspace/.bittensor/wallets/miner/

# Check mount point
ls -la /root/.bittensor/wallets/miner/

# Verify permissions
chmod 600 /workspace/.bittensor/wallets/miner/coldkey
chmod 600 /workspace/.bittensor/wallets/miner/hotkeys/miner
```

### vLLM Server Not Starting

**Symptoms:**
```
Connection refused to http://localhost:8000/v1
```

**Solutions:**

1. **If running vLLM separately**, start it first:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
     --model Qwen/Qwen2.5-14B-Instruct \
     --port 8000 \
     --gpu-memory-utilization 0.9
   ```

2. **Check if model needs to be downloaded:**
   ```bash
   # Models download on first run, can take 10-30 minutes
   tail -f /app/logs/vllm-server.log
   ```

3. **Adjust GPU memory:**
   ```bash
   # In .env, lower GPU_MEMORY_UTILIZATION
   GPU_MEMORY_UTILIZATION=0.8
   ```

### Out of Memory (OOM)

**Symptoms:**
```
CUDA out of memory
RuntimeError: out of memory
```

**Solutions:**

1. **Use smaller model:**
   ```bash
   # In .env
   DEFAULT_MODEL=Qwen/Qwen2.5-7B-Instruct
   ```

2. **Reduce context length:**
   ```bash
   MAX_MODEL_LEN=2048
   ```

3. **Lower GPU utilization:**
   ```bash
   GPU_MEMORY_UTILIZATION=0.7
   ```

4. **Use quantized model:**
   ```bash
   DEFAULT_MODEL=Qwen/Qwen2.5-14B-Instruct-AWQ
   ```

### Network Connection Issues

**Symptoms:**
```
Failed to connect to wss://entrypoint-finney.opentensor.ai:443
```

**Solutions:**

1. **Check network connectivity:**
   ```bash
   curl https://entrypoint-finney.opentensor.ai
   ```

2. **Verify firewall rules** in RunPod

3. **Try alternative endpoint:**
   ```bash
   SUBTENSOR_ADDRESS=wss://finney.subtensor.network:443
   ```

### Pod Crashes or Restarts

**Check:**

1. **Pod logs** in RunPod dashboard
2. **GPU availability:**
   ```bash
   nvidia-smi
   ```
3. **Disk space:**
   ```bash
   df -h /workspace
   ```
4. **Memory usage:**
   ```bash
   free -h
   ```

### Model Download Slow/Stuck

**Solutions:**

1. **Enable HuggingFace fast transfer:**
   ```bash
   pip install hf_transfer
   export HF_HUB_ENABLE_HF_TRANSFER=1
   ```

2. **Use cached models** (if available on volume)

3. **Pre-download models:**
   ```bash
   python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-14B-Instruct')"
   ```

## Cost Optimization

### GPU Selection

| GPU | VRAM | Cost/Hour (On-Demand) | Cost/Hour (Spot) | Recommended Model |
|-----|------|----------------------|------------------|-------------------|
| RTX 3090 | 24GB | $0.30 | $0.15 | Qwen2.5-7B |
| RTX 4090 | 24GB | $0.35 | $0.18 | Qwen2.5-7B |
| A10 | 24GB | $0.40 | $0.20 | Qwen2.5-14B |
| A40 | 48GB | $0.60 | $0.30 | Qwen2.5-32B |
| A100 40GB | 40GB | $1.00 | $0.50 | Qwen2.5-32B |
| A100 80GB | 80GB | $1.50 | $0.75 | Qwen2.5-72B |

*Prices are approximate and vary by region*

### Cost-Saving Tips

1. **Use Spot Instances:**
   - Save 50-70% vs on-demand
   - Good for mining (can tolerate interruptions)
   - Enable auto-restart on termination

2. **Choose Right-Sized GPU:**
   - Don't overpay for unused VRAM
   - Start with smaller GPU, scale up if needed

3. **Use Model Caching:**
   - Store models on network volume
   - Avoid re-downloading on pod restart
   - Set `HUGGINGFACE_HUB_CACHE=/workspace/models`

4. **Optimize Context Length:**
   - Lower `MAX_MODEL_LEN` = less memory = can use smaller GPU
   - Test what context length you actually need

5. **Stop When Not Mining:**
   - Stop pod when not actively mining
   - Network volume persists (only $0.10/GB/month)
   - Restart quickly when needed

6. **Regional Pricing:**
   - Check multiple regions
   - Some regions are 20-30% cheaper
   - Consider latency to Bittensor network

## Performance Tuning

### For Maximum Throughput

```bash
# In .env
VLLM_MAX_NUM_SEQS=128
VLLM_MAX_NUM_BATCHED_TOKENS=65536
GPU_MEMORY_UTILIZATION=0.95
VLLM_ENABLE_PREFIX_CACHING=true
```

### For Lower Latency

```bash
# In .env
VLLM_MAX_NUM_SEQS=32
VLLM_MAX_NUM_BATCHED_TOKENS=16384
GPU_MEMORY_UTILIZATION=0.85
```

### For Stability

```bash
# In .env
GPU_MEMORY_UTILIZATION=0.8
MAX_MODEL_LEN=4096
VLLM_MAX_NUM_SEQS=64
```

## Security Best Practices

1. **Wallet Security:**
   - Use read-only mounts (`:ro`) for wallet files
   - Never expose wallet files in Docker images
   - Keep backup of seed phrases offline
   - Consider using separate coldkey and hotkey

2. **Network Security:**
   - Don't expose unnecessary ports
   - Use RunPod's firewall features
   - Monitor for unusual activity

3. **API Security:**
   - Don't expose miner API publicly unless necessary
   - Consider adding authentication if public
   - Monitor API access logs

4. **Environment Variables:**
   - Don't commit .env to git
   - Use RunPod's secret management when possible
   - Rotate API keys regularly

## Maintenance

### Regular Tasks

**Daily:**
- Check miner is running and responding
- Monitor GPU utilization
- Review logs for errors

**Weekly:**
- Check TAO balance and rewards
- Update model if needed
- Review performance metrics
- Check for software updates

**Monthly:**
- Update Docker image to latest version
- Review and optimize costs
- Backup wallet seed phrases
- Clean up old logs and cache files

### Updating Miner

```bash
# Build new image locally
docker build -t yourusername/loosh-miner:runpod .
docker push yourusername/loosh-miner:runpod

# In RunPod:
# 1. Stop current pod
# 2. Deploy new pod with updated image
# 3. Network volume data persists automatically
```

## Support and Resources

- **Documentation:** [README.md](README.md)
- **Quickstart:** [MINER_QUICKSTART.md](MINER_QUICKSTART.md)
- **GitHub Issues:** https://github.com/Loosh-ai/loosh-inference-miner/issues
- **Model Specs:** [min_compute.yml](min_compute.yml)
- **RunPod Docs:** https://docs.runpod.io/
- **Bittensor Docs:** https://docs.bittensor.com/

## Example: Complete Deployment Checklist

- [ ] Build Docker image for RunPod
- [ ] Push image to registry (Docker Hub/GHCR)
- [ ] Create RunPod network volume (50-100GB)
- [ ] Deploy temporary pod with volume attached
- [ ] Upload wallet files to `/workspace/.bittensor/wallets/`
- [ ] Set wallet file permissions (chmod 600)
- [ ] Create `.env` file at `/workspace/.env`
- [ ] Configure environment for your GPU
- [ ] Stop temporary pod
- [ ] Deploy production miner pod
- [ ] Attach network volume at `/workspace`
- [ ] Configure volume mounts for wallet and .env
- [ ] Expose ports 8000 and 8089
- [ ] Start pod and wait for initialization
- [ ] Verify wallet access with `btcli wallet overview`
- [ ] Test miner API health endpoint
- [ ] Check subnet registration
- [ ] Monitor logs for any errors
- [ ] Set up monitoring and alerts
- [ ] Document your configuration

## Conclusion

You now have a complete guide for deploying the Loosh Inference Miner on RunPod. The combination of RunPod's GPU infrastructure and network volumes provides a reliable, cost-effective platform for running your miner.

Key takeaways:
- Use the `runpod` build environment for optimal compatibility
- Store wallets and config on network volumes for persistence
- Choose GPU based on model size and budget
- Use spot instances for significant cost savings
- Monitor regularly and optimize for your use case

Happy mining! 🚀
