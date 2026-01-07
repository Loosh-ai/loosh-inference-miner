# LLM Service Backends

Modular LLM service implementation supporting multiple backends: vLLM, Ollama, and llama.cpp. Backends are registered via entry points and can be easily extended.

## Installation

### Install with UV

The project uses UV for dependency management. Install with specific backend dependencies:

```bash
# Install with vLLM backend
uv pip install -e ".[vllm]"

# Install with Ollama backend (httpx is already included)
uv pip install -e ".[ollama]"

# Install with llama.cpp backend
uv pip install -e ".[llamacpp]"

# Install with all backends
uv pip install -e ".[all]"
```

### Using UV sync (recommended)

```bash
# For vLLM
uv sync --extra vllm

# For Ollama
uv sync --extra ollama

# For llama.cpp
uv sync --extra llamacpp

# For all backends
uv sync --extra all
```

### Standard pip installation

```bash
# Install base package
pip install -e .

# Install with specific backend
pip install -e ".[vllm]"
pip install -e ".[ollama]"
pip install -e ".[llamacpp]"
pip install -e ".[all]"
```

## Configuration

Set the backend in your `.env` file or environment variables:

```bash
# Use vLLM
LLM_BACKEND=vllm

# Use Ollama
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434  # Optional, defaults to localhost

# Use llama.cpp (default)
LLM_BACKEND=llamacpp
MODEL_PATH=/path/to/model.gguf  # Optional, can use model name
```

### Configuration Options

- `LLM_BACKEND`: Backend to use (`vllm`, `ollama`, or `llamacpp`)
- `MODEL_PATH`: Path to model file (for llama.cpp)
- `OLLAMA_BASE_URL`: Ollama API base URL (default: `http://localhost:11434`)
- `OLLAMA_TIMEOUT`: Ollama API timeout in seconds (default: `300.0`)
- `TENSOR_PARALLEL_SIZE`: Number of GPU layers/parallel workers
- `GPU_MEMORY_UTILIZATION`: GPU memory utilization (0.0-1.0)
- `MAX_MODEL_LEN`: Maximum context length

## Usage

### Basic Usage

```python
from miner.config.config import MinerConfig
from miner.core.llms import get_backend

# Load configuration (reads LLM_BACKEND from env)
config = MinerConfig()

# Get backend service (automatically selects backend from config)
backend_name = getattr(config, 'llm_backend', 'llamacpp')
service = get_backend(backend_name, config)

# Generate text
response = await service.generate(
    prompt="Hello, how are you?",
    model="mistralai/Mistral-7B-v0.1",
    max_tokens=512,
    temperature=0.7,
    top_p=0.95
)

# Health check
is_healthy = await service.health_check()
```

### List Available Backends

```python
from miner.core.llms import get_backends

backends = get_backends()
print(f"Available backends: {list(backends.keys())}")
```

### Backend Fallback

If a requested backend is not found, the system will:
1. Log a warning with available backends
2. Automatically use the first available backend
3. Continue execution without raising an error

## Backend-Specific Notes

### vLLM

- **Requirements**: CUDA-capable GPU
- **Best for**: High-throughput inference
- **Features**: 
  - Tensor parallelism support
  - Efficient batching
  - Models from HuggingFace or local paths
- **Installation**: `uv pip install -e ".[vllm]"`

### Ollama

- **Requirements**: Ollama server running (local or remote)
- **Best for**: Easy deployment, no Python dependencies
- **Features**:
  - HTTP API (no Python deps required)
  - Remote server support
  - Models must be pulled in Ollama first: `ollama pull model-name`
- **Installation**: `uv pip install -e ".[ollama]"` (httpx already included)
- **Setup**: 
  ```bash
  # Install Ollama (if not already installed)
  curl -fsSL https://ollama.com/install.sh | sh
  
  # Pull a model
  ollama pull mistral
  ```

### llama.cpp

- **Requirements**: CPU or GPU (CUDA/OpenCL)
- **Best for**: Resource-constrained environments
- **Features**:
  - Works on CPU and GPU
  - GGUF model format
  - Low memory footprint
- **Installation**: `uv pip install -e ".[llamacpp]"`
- **Model Format**: Requires GGUF format models

## Adding a New Backend

1. Create a new backend file (e.g., `llm_newbackend.py`) in `miner/core/llms/`
2. Inherit from `LLMService` and implement required methods:

```python
from miner.core.llms.LLMService import LLMService

class NewBackendService(LLMService):
    def __init__(self, config):
        super().__init__(config)
        # Initialize your backend
    
    async def generate(self, prompt, model, max_tokens, temperature, top_p):
        # Implement generation logic
        pass
    
    async def _get_model(self, model_name):
        # Implement model loading
        pass
    
    async def health_check(self):
        # Optional: implement health check
        return True
```

3. Register in `pyproject.toml`:

```toml
[project.entry-points."inference.backends"]
newbackend = "miner.core.llms.llm_newbackend:NewBackendService"
```

4. Add optional dependencies if needed:

```toml
[project.optional-dependencies]
newbackend = [
    "new-backend-package>=1.0.0",
]
```

The backend will be automatically discovered and available via `get_backend()`.

## Entry Points

Backends are registered using Python entry points in `pyproject.toml`:

```toml
[project.entry-points."inference.backends"]
vllm = "miner.core.llms.llm_vllm:VLLMService"
ollama = "miner.core.llms.llm_ollama:OllamaService"
llamacpp = "miner.core.llms.llm_llamacpp:LlamaCppService"
```

This allows:
- Dynamic backend discovery
- Third-party packages to register their own backends
- No code changes needed when adding new backends

## Running Tests

See `miner/core/tests/` for installation and runtime tests:

```bash
# Run all tests
pytest miner/core/tests/

# Run specific test
pytest miner/core/tests/test_llm_install.py
pytest miner/core/tests/test_llm_run.py
```

## Troubleshooting

### Backend not found

If you see "Backend 'X' not found", check:
1. Entry points are correctly registered in `pyproject.toml`
2. Package is installed: `pip install -e .` or `uv pip install -e .`
3. Backend dependencies are installed: `uv pip install -e ".[backend_name]"`

### Import errors

If you see import errors for backend-specific packages:
- Install the backend dependencies: `uv pip install -e ".[backend_name]"`
- For vLLM: Ensure CUDA is properly installed
- For llama.cpp: Ensure `llama-cpp-python` is installed with correct GPU support

### Ollama connection errors

- Ensure Ollama server is running: `ollama serve`
- Check `OLLAMA_BASE_URL` matches your Ollama server address
- Verify network connectivity to Ollama server

