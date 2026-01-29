# ---------- base stage ----------

# ARGs for build-time configuration - must be declared before any FROM that uses them
ARG OPTIONAL_DEPS=llamacpp
ARG BUILD_ENV=dev

# Use BUILD_ENV=dev for ubuntu:24.04, 
# BUILD_ENV=cuda for nvidia/cuda docker (Ubuntu 24.04 with CUDA 13.1.1)
# BUILD_ENV=runpod for runpod

FROM ubuntu:24.04 AS base-dev
FROM nvidia/cuda:12.9.1-base-ubuntu24.04 AS base-cuda
FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404 AS base-runpod

FROM base-${BUILD_ENV} AS base

WORKDIR /app

# Install system dependencies and Python 3.12
# All base images (Ubuntu 24.04) have Python 3.12 available directly
# Note: libxcb1, libglib2.0-0 are required by opencv-python-headless (pulled by vllm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    telnet \
    vim \
    socat \
    gcc \
    g++ \
    make \
    cmake \
    curl \
    git \
    supervisor \
    libxcb1 \
    libglib2.0-0 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && mkdir -p /var/log/supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip3 install uv --break-system-packages \
    && rm -rf /root/.cache/pip

# Copy dependency files
COPY pyproject.toml setup.py ./

# Create wallet directory (wallets will be mounted at runtime via volumes)
RUN mkdir -p /root/.bittensor/wallets/miner

# Accept venv name as build argument (unique per container)
ARG VENV_NAME=.venv-docker

# Create virtual environment with custom name for docker
RUN uv venv $VENV_NAME

# Set environment variable to use the venv
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME

# Sync base dependencies with uv
RUN uv sync

# Clone and install fiber package from git repository into the venv
# Install AFTER uv sync to ensure it's in the venv and not overwritten
RUN git clone --branch production --depth 1 https://github.com/rayonlabs/fiber.git /tmp/fiber && \
    uv pip install -p $VENV_NAME "/tmp/fiber[chain]" && \
    rm -rf /tmp/fiber

# Install btcli (Bittensor CLI) for wallet management
RUN uv pip install -p $VENV_NAME --system bittensor && \
    ln -sf $VENV_NAME/bin/btcli /usr/local/bin/btcli || \
    (echo '#!/bin/bash' > /usr/local/bin/btcli && \
     echo "uv run btcli \"\$@\"" >> /usr/local/bin/btcli && \
     chmod +x /usr/local/bin/btcli)

# Clean up all caches to reduce image size
RUN rm -rf /root/.cache/uv \
           /root/.uv-cache \
           /root/.cache/pip \
           /root/.cache/torch \
           /root/.nv/ComputeCache \
           /root/.cache/huggingface \
           /tmp/*

# ---------- vllm stage ----------
FROM base AS with-vllm
ARG VENV_NAME=.venv-docker
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME
RUN uv pip install -p $VENV_NAME -e ".[vllm]" && \
    rm -rf /root/.cache/uv \
           /root/.uv-cache \
           /root/.cache/pip \
           /root/.cache/torch \
           /root/.nv/ComputeCache \
           /root/.cache/huggingface \
           /tmp/*

# ---------- llamacpp stage ----------
FROM base AS with-llamacpp
ARG VENV_NAME=.venv-docker
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME
#RUN uv pip install --system -e ".[llamacpp]"

# ---------- ollama stage ----------
FROM base AS with-ollama
ARG VENV_NAME=.venv-docker
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME
#RUN uv pip install --system -e ".[ollama]"


# ---------- final stage (non-vllm: single process) ----------
FROM with-${OPTIONAL_DEPS} AS final-single
ARG OPTIONAL_DEPS=llamacpp
ARG VENV_NAME=.venv-docker
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME

# Build argument for cache busting - set to current timestamp or version
# These are used in a RUN command to invalidate Docker cache for subsequent layers
ARG BUILD_TIMESTAMP
ARG BUILD_VERSION
# Use build args in RUN to invalidate cache - this layer will rebuild when args change
RUN echo "Build timestamp: ${BUILD_TIMESTAMP:-$(date -u +%Y%m%d-%H%M%S)}" > /tmp/build_info.txt && \
    echo "Build version: ${BUILD_VERSION:-dev}" >> /tmp/build_info.txt && \
    cat /tmp/build_info.txt

# Copy application code
# Copy source files in a way that invalidates cache when code changes
# Copy miner code first (most likely to change)
COPY miner/ /app/miner/
# Copy docker scripts
COPY docker/ /app/docker/
# Copy project files
COPY pyproject.toml setup.py ./
# Copy README if it exists (optional)
RUN test -f README.md && cp README.md /app/README.md || true

# Copy wallet files if they exist (optional - wallets can be mounted at runtime)
# Note: Wallets are typically mounted via volumes in docker-compose, so this is optional
RUN if [ -d "docker/wallets/miner" ] && [ "$(ls -A docker/wallets/miner 2>/dev/null)" ]; then \
        echo "Copying wallet files from docker/wallets/miner"; \
        cp -r docker/wallets/miner/* /root/.bittensor/wallets/miner/ 2>/dev/null || true; \
    else \
        echo "Note: docker/wallets/miner not found or empty, wallets will be mounted at runtime via volumes"; \
    fi

# Copy nop.sh and make it executable
COPY docker/nop.sh /app/docker/nop.sh
RUN chmod +x /app/docker/nop.sh

# Copy prompt.sh for PS1 customization
COPY docker/prompt.sh /etc/profile.d/prompt.sh

# Set PYTHONPATH
ENV PYTHONPATH="."

# Expose port
EXPOSE 8000

# Run the miner using uvicorn (single process)
# Use string reference to avoid __main__ module double-import issue
# Port and host are read from environment variables (API_HOST, API_PORT)
# WALLET_PATH can be set to persistent storage location (defaults to /workspace/.bittensor/wallets for RunPod)
CMD ["bash", "-c", "\
    source /workspace/.env 2>/dev/null || source .env 2>/dev/null || true; \
    WALLET_SOURCE=${WALLET_PATH:-/workspace/.bittensor/wallets}; \
    if [ -d \"$WALLET_SOURCE\" ] && [ \"$(ls -A $WALLET_SOURCE 2>/dev/null)\" ]; then \
        echo \"Copying wallets from $WALLET_SOURCE to /root/.bittensor/wallets\"; \
        mkdir -p /root/.bittensor/wallets; \
        cp -r $WALLET_SOURCE/* /root/.bittensor/wallets/; \
    else \
        echo \"No wallets found in $WALLET_SOURCE\"; \
    fi; \
    exec uv run uvicorn miner.miner_server:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]


# ---------- final stage (vllm: unified with supervisord) ----------
FROM with-vllm AS final-vllm
ARG VENV_NAME=.venv-docker
ENV UV_PROJECT_ENVIRONMENT=$VENV_NAME

# Build argument for cache busting - set to current timestamp or version
ARG BUILD_TIMESTAMP
ARG BUILD_VERSION
# Use build args in RUN to invalidate cache - this layer will rebuild when args change
RUN echo "Build timestamp: ${BUILD_TIMESTAMP:-$(date -u +%Y%m%d-%H%M%S)}" > /tmp/build_info.txt && \
    echo "Build version: ${BUILD_VERSION:-dev}" >> /tmp/build_info.txt && \
    cat /tmp/build_info.txt

# Copy application code
# Copy source files in a way that invalidates cache when code changes
# Copy miner code first (most likely to change)
COPY miner/ /app/miner/
# Copy docker scripts
COPY docker/ /app/docker/
# Copy project files
COPY pyproject.toml setup.py ./
# Copy README if it exists (optional)
RUN test -f README.md && cp README.md /app/README.md || true

# Copy wallet files if they exist (optional - wallets can be mounted at runtime)
# Note: Wallets are typically mounted via volumes in docker-compose, so this is optional
RUN if [ -d "docker/wallets/miner" ] && [ "$(ls -A docker/wallets/miner 2>/dev/null)" ]; then \
        echo "Copying wallet files from docker/wallets/miner"; \
        cp -r docker/wallets/miner/* /root/.bittensor/wallets/miner/ 2>/dev/null || true; \
    else \
        echo "Note: docker/wallets/miner not found or empty, wallets will be mounted at runtime via volumes"; \
    fi

# Copy supervisord configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy nop.sh and make it executable
COPY docker/nop.sh /app/docker/nop.sh
RUN chmod +x /app/docker/nop.sh

# Copy prompt.sh for PS1 customization
COPY docker/prompt.sh /etc/profile.d/prompt.sh

# Set PYTHONPATH
ENV PYTHONPATH="."

# Expose ports (8000 for miner API, 8001 internal for vLLM)
EXPOSE 8000

# Set default environment for vLLM
ENV LLM_BACKEND=vllm \
    VLLM_API_BASE=http://127.0.0.1:8001/v1 \
    DEFAULT_MODEL=mistralai/Mistral-7B-Instruct-v0.2 \
    TENSOR_PARALLEL_SIZE=1 \
    GPU_MEMORY_UTILIZATION=0.9 \
    MAX_MODEL_LEN=4096

# Use supervisord for multi-process container
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

