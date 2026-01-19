#!/bin/bash
# Run miner with LLM backend support (vLLM, Ollama, or llama.cpp)
# Reads configuration from .env file

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env file if it exists
# Standard approach: set -a auto-exports, then source the file
if [ -f .env ]; then
    set -a  # Automatically export all variables
    source .env 2>/dev/null || true
    set +a  # Stop automatically exporting
fi

# Default values
LLM_BACKEND=${LLM_BACKEND:-llamacpp}
API_HOST=${API_HOST:-0.0.0.0}
API_PORT=${API_PORT:-8000}
DEFAULT_MODEL=${DEFAULT_MODEL:-mistralai/Mistral-7B-v0.1}
VLLM_API_BASE=${VLLM_API_BASE:-http://localhost:8000/v1}
VLLM_PORT=${VLLM_PORT:-8000}
TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE:-1}
GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.9}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-4096}

# vLLM Advanced Configuration
VLLM_ENABLE_AUTO_TOOL_CHOICE=${VLLM_ENABLE_AUTO_TOOL_CHOICE:-true}
VLLM_TOOL_CALL_PARSER=${VLLM_TOOL_CALL_PARSER:-hermes}
VLLM_ENABLE_PREFIX_CACHING=${VLLM_ENABLE_PREFIX_CACHING:-true}
VLLM_MAX_NUM_SEQS=${VLLM_MAX_NUM_SEQS:-64}
VLLM_MAX_NUM_BATCHED_TOKENS=${VLLM_MAX_NUM_BATCHED_TOKENS:-32768}

# Create logs directory early (before any logging)
mkdir -p logs

echo "Starting Loosh Inference Miner with backend: $LLM_BACKEND"

# Function to check if a port is in use
check_port() {
    local port=$1
    if command -v lsof > /dev/null 2>&1; then
        lsof -i :$port > /dev/null 2>&1
    elif command -v netstat > /dev/null 2>&1; then
        netstat -an | grep -q ":$port.*LISTEN"
    else
        # Fallback: try to connect
        timeout 1 bash -c "cat < /dev/null > /dev/tcp/localhost/$port" 2>/dev/null
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local url=$1
    local max_attempts=30
    local attempt=0
    
    echo "Waiting for service at $url to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "Service at $url is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo "Warning: Service at $url did not become ready after $max_attempts attempts"
    return 1
}

# Handle vLLM backend
if [ "$LLM_BACKEND" = "vllm" ]; then
    echo "vLLM backend selected"
    
    # Extract port from VLLM_API_BASE if it contains a port
    if [[ "$VLLM_API_BASE" =~ :([0-9]+) ]]; then
        VLLM_PORT="${BASH_REMATCH[1]}"
    fi
    
    # Check if vLLM server is already running
    if check_port $VLLM_PORT; then
        echo "vLLM server appears to be running on port $VLLM_PORT"
        # Verify it's actually vLLM by checking the models endpoint
        if curl -s "$VLLM_API_BASE/models" > /dev/null 2>&1; then
            echo "vLLM server is ready at $VLLM_API_BASE"
        else
            echo "Warning: Port $VLLM_PORT is in use but may not be vLLM server"
            echo "Please ensure vLLM server is running at $VLLM_API_BASE"
        fi
    else
        # Build vLLM command arguments
        VLLM_ARGS="--model $DEFAULT_MODEL"
        VLLM_ARGS="$VLLM_ARGS --tensor-parallel-size $TENSOR_PARALLEL_SIZE"
        VLLM_ARGS="$VLLM_ARGS --gpu-memory-utilization $GPU_MEMORY_UTILIZATION"
        VLLM_ARGS="$VLLM_ARGS --max-model-len $MAX_MODEL_LEN"
        VLLM_ARGS="$VLLM_ARGS --port $VLLM_PORT"
        
        # Add optional flags if enabled
        if [ "$VLLM_ENABLE_AUTO_TOOL_CHOICE" = "true" ]; then
            VLLM_ARGS="$VLLM_ARGS --enable-auto-tool-choice"
        fi
        
        if [ -n "$VLLM_TOOL_CALL_PARSER" ] && [ "$VLLM_TOOL_CALL_PARSER" != "none" ]; then
            VLLM_ARGS="$VLLM_ARGS --tool-call-parser $VLLM_TOOL_CALL_PARSER"
        fi
        
        if [ "$VLLM_ENABLE_PREFIX_CACHING" = "true" ]; then
            VLLM_ARGS="$VLLM_ARGS --enable-prefix-caching"
        fi
        
        if [ -n "$VLLM_MAX_NUM_SEQS" ]; then
            VLLM_ARGS="$VLLM_ARGS --max-num-seqs $VLLM_MAX_NUM_SEQS"
        fi
        
        if [ -n "$VLLM_MAX_NUM_BATCHED_TOKENS" ]; then
            VLLM_ARGS="$VLLM_ARGS --max-num-batched-tokens $VLLM_MAX_NUM_BATCHED_TOKENS"
        fi
        
        echo "Starting vLLM server with model: $DEFAULT_MODEL"
        echo "Command: python -m vllm.entrypoints.openai.api_server $VLLM_ARGS"
        echo ""
        echo "Note: vLLM exposes an OpenAI-compatible API but does NOT require OpenAI models."
        echo "      You can use any model compatible with vLLM (HuggingFace, local, etc.)."
        echo ""
        echo "Note: If this is the first time running this model, vLLM will download it from HuggingFace."
        echo "Download progress will be shown below. This may take several minutes depending on model size."
        echo ""
        
        # Check for hf_transfer issue and handle it
        # If HF_HUB_ENABLE_HF_TRANSFER is set but hf_transfer is not installed, disable it
        PYTHON_CHECK="${PYTHON_BIN:-python}"
        if [ "${HF_HUB_ENABLE_HF_TRANSFER:-0}" = "1" ] && ! $PYTHON_CHECK -c "import hf_transfer" 2>/dev/null; then
            echo "Warning: HF_HUB_ENABLE_HF_TRANSFER=1 is set but hf_transfer is not installed."
            echo "Disabling fast download to use standard download method."
            echo ""
            echo "Note: For large models like $DEFAULT_MODEL (72B), installing hf_transfer can significantly"
            echo "      speed up downloads. To enable fast downloads, run:"
            echo "      pip install hf_transfer"
            echo "      or: uv pip install hf_transfer"
            echo ""
            export HF_HUB_ENABLE_HF_TRANSFER=0
        fi
        
        # Set HuggingFace cache location if specified
        # Default location: ~/.cache/huggingface/hub/
        # Can be overridden via HUGGINGFACE_HUB_CACHE or HF_HOME environment variables
        if [ -n "${HUGGINGFACE_HUB_CACHE:-}" ]; then
            export HUGGINGFACE_HUB_CACHE
            echo "Using custom HuggingFace cache: $HUGGINGFACE_HUB_CACHE"
            # Ensure the directory exists
            mkdir -p "$HUGGINGFACE_HUB_CACHE"
        elif [ -n "${HF_HOME:-}" ]; then
            export HF_HOME
            echo "Using custom HuggingFace home: $HF_HOME (cache will be in $HF_HOME/hub/)"
            # Ensure the directory exists
            mkdir -p "$HF_HOME/hub"
        else
            # Show default location
            DEFAULT_CACHE="${HOME}/.cache/huggingface/hub"
            echo "HuggingFace cache location: $DEFAULT_CACHE"
            echo "  (To change this, set HUGGINGFACE_HUB_CACHE or HF_HOME in your .env file)"
        fi
        
        # Start vLLM server in background
        # Use stdbuf to ensure unbuffered output, and tee to show progress while logging
        # PYTHONUNBUFFERED=1 ensures progress bars show in real-time
        # We redirect to both stdout (for user to see) and log file
        
        # Determine the Python interpreter to use
        # Prefer venv python, fall back to uv run python, then system python
        if [ -f ".venv/bin/python" ]; then
            PYTHON_BIN=".venv/bin/python"
            echo "Using venv Python: $PYTHON_BIN"
        elif command -v uv &> /dev/null; then
            PYTHON_BIN="uv run python"
            echo "Using uv run python"
        else
            PYTHON_BIN="python"
            echo "Warning: Using system Python. vLLM may not be installed."
            echo "Install with: uv sync --extra vllm"
        fi
        
        # Start vLLM with output going to both terminal and log file
        # Use unbuffer or script to preserve TTY for progress bars
        # Force tqdm to show progress even when piped
        echo ""
        echo "Starting vLLM server (output will appear below)..."
        echo "Progress bars from model download will be displayed."
        echo ""
        
        # Start vLLM - use script -c to preserve TTY for progress bars, or fall back to tee
        if command -v script &> /dev/null; then
            # Use script command to preserve TTY (better for progress bars)
            # Different syntax for Linux vs macOS
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                (
                    PYTHONUNBUFFERED=1 HF_HUB_DISABLE_PROGRESS_BARS=0 \
                    script -q logs/vllm-server.log $PYTHON_BIN -m vllm.entrypoints.openai.api_server $VLLM_ARGS
                ) &
            else
                # Linux
                (
                    PYTHONUNBUFFERED=1 HF_HUB_DISABLE_PROGRESS_BARS=0 \
                    script -q -c "$PYTHON_BIN -m vllm.entrypoints.openai.api_server $VLLM_ARGS" logs/vllm-server.log
                ) &
            fi
        else
            # Fallback to tee with forced progress
            # Set environment to force tqdm progress bars
            (
                PYTHONUNBUFFERED=1 HF_HUB_DISABLE_PROGRESS_BARS=0 FORCE_COLOR=1 \
                $PYTHON_BIN -u -m vllm.entrypoints.openai.api_server $VLLM_ARGS \
                    2>&1 | tee logs/vllm-server.log
            ) &
        fi
        
        VLLM_PID=$!
        echo "vLLM server started with PID: $VLLM_PID"
        echo "Logs are being written to: logs/vllm-server.log"
        echo "Waiting for vLLM server to be ready (this may take a while if downloading the model)..."
        
        # Give vLLM a moment to start and potentially show errors
        sleep 3
        
        # Check if the process is still running
        if ! kill -0 $VLLM_PID 2>/dev/null; then
            echo ""
            echo "Error: vLLM server process died immediately!"
            echo "This usually indicates a configuration error or missing dependencies."
            echo ""
            # Wait a moment for output to be written
            sleep 2
            if [ -f logs/vllm-server.log ] && [ -s logs/vllm-server.log ]; then
                echo "Error output from vLLM:"
                echo "----------------------------------------"
                cat logs/vllm-server.log
                echo "----------------------------------------"
            else
                echo "No error output captured. Possible issues:"
                echo "  - vLLM not installed: Run 'uv sync --extra vllm'"
                echo "  - Using wrong Python interpreter: Ensure .venv exists and contains vLLM"
                echo "  - Model not found or invalid: Check model name '$DEFAULT_MODEL'"
                echo "    Note: For AWQ models, ensure the model path is correct"
                echo "    Example: 'Qwen/Qwen2.5-72B-Instruct-AWQ' or use base model with quantization"
                echo "  - hf_transfer issue: If HF_HUB_ENABLE_HF_TRANSFER=1, install: pip install hf_transfer"
                echo "    Or disable it: unset HF_HUB_ENABLE_HF_TRANSFER"
                echo "  - GPU/CUDA issues: Check CUDA installation and GPU availability"
                echo "  - Port already in use: Check if port $VLLM_PORT is available"
                echo ""
                echo "Verify vLLM installation:"
                echo "  ${PYTHON_BIN:-python} -c 'import vllm; print(vllm.__version__)'"
                echo ""
                echo "Try running vLLM manually to see the error:"
                echo "  ${PYTHON_BIN:-python} -m vllm.entrypoints.openai.api_server --model $DEFAULT_MODEL --port $VLLM_PORT"
            fi
            exit 1
        fi
        
        # Wait for vLLM to be ready
        wait_for_service "$VLLM_API_BASE/models" || {
            echo ""
            echo "Error: vLLM server failed to start or did not become ready"
            echo "Process PID $VLLM_PID status:"
            if kill -0 $VLLM_PID 2>/dev/null; then
                echo "  Process is still running (may still be loading model)"
                echo "  Check logs/vllm-server.log for progress"
            else
                echo "  Process has exited"
            fi
            echo ""
            # Show recent log output
            if [ -f logs/vllm-server.log ] && [ -s logs/vllm-server.log ]; then
                echo "Last 50 lines of log file:"
                echo "----------------------------------------"
                tail -50 logs/vllm-server.log
                echo "----------------------------------------"
                echo ""
                # Check for common errors and provide solutions
                if grep -q "hf_transfer" logs/vllm-server.log 2>/dev/null; then
                    echo "Solution: Install hf_transfer or disable fast download:"
                    echo "  pip install hf_transfer"
                    echo "  OR"
                    echo "  unset HF_HUB_ENABLE_HF_TRANSFER"
                    echo ""
                fi
                if grep -q "Can't load the configuration" logs/vllm-server.log 2>/dev/null; then
                    echo "Solution: Check if the model name is correct:"
                    echo "  - For AWQ models, verify the model path exists on HuggingFace"
                    echo "  - Try using the base model name instead: 'Qwen/Qwen2.5-72B-Instruct'"
                    echo "  - Or check if you need to specify quantization differently"
                    echo ""
                fi
                if grep -q "Disk quota exceeded\|No space left\|ENOSPC" logs/vllm-server.log 2>/dev/null; then
                    echo "Solution: Disk space issue detected. Options:"
                    echo "  1. Free up space in the current cache location"
                    echo "  2. Set a custom cache location with more space in your .env file:"
                    echo "     HUGGINGFACE_HUB_CACHE=/path/to/larger/disk/huggingface-cache"
                    echo "  3. Or set HF_HOME to change the base directory:"
                    echo "     HF_HOME=/path/to/larger/disk/huggingface"
                    echo ""
                    echo "  Current cache location: ${HUGGINGFACE_HUB_CACHE:-${HF_HOME:-$HOME/.cache/huggingface}/hub}"
                    echo ""
                fi
            else
                echo "Log file is empty - process may have failed immediately"
            fi
            kill $VLLM_PID 2>/dev/null || true
            exit 1
        }
        
        echo "vLLM server is ready!"
        
        # Trap to cleanup vLLM on script exit
        trap "echo 'Stopping vLLM server...'; kill $VLLM_PID 2>/dev/null || true" EXIT
    fi
fi

# Handle Ollama backend
if [ "$LLM_BACKEND" = "ollama" ]; then
    echo "Ollama backend selected"
    
    OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
    
    # Check if Ollama is running
    if ! curl -s "$OLLAMA_BASE_URL/api/tags" > /dev/null 2>&1; then
        echo "Warning: Ollama server does not appear to be running at $OLLAMA_BASE_URL"
        echo "Please start Ollama server first: ollama serve"
        echo "Or pull your model: ollama pull $DEFAULT_MODEL"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo "Ollama server is running at $OLLAMA_BASE_URL"
    fi
fi

# Handle llama.cpp backend
if [ "$LLM_BACKEND" = "llamacpp" ]; then
    echo "llama.cpp backend selected (runs in-process)"
    if [ -z "$MODEL_PATH" ]; then
        echo "Warning: MODEL_PATH is not set. The model will need to be specified at runtime."
    fi
fi

# Start the miner
echo "Starting miner server on $API_HOST:$API_PORT..."
PYTHONPATH=. uv run uvicorn miner.miner_server:app --host "$API_HOST" --port "$API_PORT" --reload

