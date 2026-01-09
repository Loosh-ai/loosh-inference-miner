#!/bin/bash
# Deploy Miner to RunPod via SSH
# Usage: ./deploy.sh <runpod_ssh_host> [runpod_ssh_port] [options]
#
# Options:
#   --copy         Copy project files to remote (default: skip, use existing /app)
#   --setup-base   Install base apt packages and Python dependencies
#   --zip          Just create deploy.tar.gz (no deployment)

set -e
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Parse options
COPY_FILES=false
SETUP_BASE=false
ZIP_ONLY=false
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --copy)
            COPY_FILES=true
            shift
            ;;
        --setup-base)
            SETUP_BASE=true
            shift
            ;;
        --zip)
            ZIP_ONLY=true
            shift
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

set -- "${POSITIONAL_ARGS[@]}"

# RunPod SSH configuration
RUNPOD_HOST="${1:-}"
RUNPOD_PORT="${2:-22}"
REMOTE_DIR="${REMOTE_DIR:-/app}"

# Handle --zip option (doesn't require host)
if [ "$ZIP_ONLY" = true ]; then
    echo "=========================================="
    echo "Creating deploy.tar.gz"
    echo "=========================================="
    TAR_FILE="${SCRIPT_DIR}/deploy.tar.gz"
    rm -f "${TAR_FILE}"
    cd "${PROJECT_ROOT}"
    tar -czvf "${TAR_FILE}" \
        --exclude='.git' \
        --exclude='.venv*' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='*.db' \
        --exclude='*.log' \
        --exclude='logs' \
        --exclude='docker' \
        --exclude='deploy' \
        --exclude='.env' \
        .
    echo ""
    echo "Created: ${TAR_FILE}"
    echo "Size: $(du -h "${TAR_FILE}" | cut -f1)"
    exit 0
fi

if [ -z "$RUNPOD_HOST" ]; then
    echo "Usage: $0 <runpod_ssh_host> [runpod_ssh_port] [options]"
    echo ""
    echo "Options:"
    echo "  --copy         Copy project files to remote (default: skip, use existing /app)"
    echo "  --setup-base   Install base apt packages and Python dependencies"
    echo "  --zip          Just create deploy.tar.gz (no deployment)"
    echo ""
    echo "Examples:"
    echo "  $0 ssh.runpod.io 22345                    # Config only (files already in /app)"
    echo "  $0 ssh.runpod.io 22345 --copy             # Full deploy with file copy"
    echo "  $0 ssh.runpod.io 22345 --setup-base       # Install base deps + deploy"
    echo "  $0 --zip                                  # Just create deploy.tar.gz"
    exit 1
fi

echo "=========================================="
echo "Deploying Miner to RunPod"
echo "=========================================="
echo "Host: ${RUNPOD_HOST}:${RUNPOD_PORT}"
echo "Remote Dir: ${REMOTE_DIR}"
echo "Copy Files: ${COPY_FILES}"
echo "Setup Base: ${SETUP_BASE}"
echo "Zip Only: ${ZIP_ONLY}"
echo ""

STEP=1

# Setup base dependencies if requested
if [ "$SETUP_BASE" = true ]; then
    echo "[${STEP}] Installing base apt packages and Python dependencies..."
    ssh -p "${RUNPOD_PORT}" "${RUNPOD_HOST}" << 'SETUP_SCRIPT'
# Install system dependencies and Python 3.12
apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    openssh-client \
    telnet \
    vim \
    socat \
    gcc \
    g++ \
    make \
    cmake \
    curl \
    git \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3

# Install uv
pip3 install uv --break-system-packages

echo "Base setup complete!"
SETUP_SCRIPT
    ((STEP++))
fi

# Create remote directory
echo "[${STEP}] Creating remote directory..."
ssh -p "${RUNPOD_PORT}" "${RUNPOD_HOST}" "mkdir -p ${REMOTE_DIR}"
((STEP++))

# Sync project files (excluding unnecessary files)
if [ "$COPY_FILES" = true ]; then
    echo "[${STEP}] Syncing project files..."
    rsync -avz --progress \
        --exclude='.git' \
        --exclude='.venv*' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='*.db' \
        --exclude='*.log' \
        --exclude='logs/' \
        --exclude='docker/' \
        --exclude='deploy/' \
        --exclude='.env' \
        -e "ssh -p ${RUNPOD_PORT}" \
        "${PROJECT_ROOT}/" \
        "${RUNPOD_HOST}:${REMOTE_DIR}/"
    ((STEP++))
else
    echo "[${STEP}] Skipping file sync (use --copy to enable)..."
    ((STEP++))
fi

# Copy miner configuration if env file exists
if [ -f "${SCRIPT_DIR}/miner.env" ]; then
    echo "[${STEP}] Copying miner configuration..."
    cat "${SCRIPT_DIR}/miner.env" | ssh -p "${RUNPOD_PORT}" "${RUNPOD_HOST}" "cat > ${REMOTE_DIR}/.env"
    ((STEP++))
else
    echo "[${STEP}] No miner.env file found, skipping configuration copy..."
    echo "Create ${SCRIPT_DIR}/miner.env with your environment variables"
    ((STEP++))
fi

# Setup and start miner
echo "[${STEP}] Setting up and starting miner..."
ssh -p "${RUNPOD_PORT}" "${RUNPOD_HOST}" "REMOTE_DIR=${REMOTE_DIR}" << 'REMOTE_SCRIPT'
cd "${REMOTE_DIR:-/app}"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv || uv venv .venv
fi

# Activate venv and install dependencies
echo "Installing dependencies..."
source .venv/bin/activate 2>/dev/null || true
pip install -e . || uv pip install -e .

# Clone and install fiber if not present
if [ ! -d "fiber" ] && ! pip show fiber >/dev/null 2>&1; then
    echo "Installing fiber..."
    git clone --branch production --depth 1 https://github.com/rayonlabs/fiber.git /tmp/fiber
    pip install "/tmp/fiber[chain]" || uv pip install "/tmp/fiber[chain]"
    rm -rf /tmp/fiber
fi

# Start miner
echo "Starting miner..."
nohup python -m miner.main > miner.log 2>&1 &
echo "Miner started with PID: $!"

# Show status
sleep 2
ps aux | grep -E "miner.main" | grep -v grep || echo "Warning: Miner process not found"
REMOTE_SCRIPT

echo ""
echo "=========================================="
echo "Miner deployment complete!"
echo "=========================================="
echo "SSH in to check logs: ssh -p ${RUNPOD_PORT} ${RUNPOD_HOST}"
echo "Log file: ${REMOTE_DIR}/miner.log"

