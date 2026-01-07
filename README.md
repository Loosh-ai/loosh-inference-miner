# Loosh Inference Miner

A Bittensor subnet miner for LLM inference. This miner runs LLM inference workloads and responds to challenges from validators.

## Project Structure

```
loosh-inference-miner/
├── miner/                    # Miner code
│   ├── core/                # Core miner functionality
│   │   ├── llms/           # LLM backend implementations
│   │   └── configuration.py # Configuration management
│   ├── endpoints/          # API endpoints
│   │   ├── inference.py    # Inference endpoint
│   │   └── availability.py # Availability endpoint
│   ├── network/            # Bittensor network code
│   │   ├── InferenceSynapse.py # Synapse definition
│   │   ├── bittensor_node.py # Bittensor node implementation
│   │   └── axon.py         # Axon implementation
│   ├── config/             # Configuration
│   │   ├── config.py       # Miner configuration
│   │   └── shared_config.py # Shared config utilities
│   └── main.py            # Miner entry point
├── docker/                  # Docker configuration
│   ├── Dockerfile          # Main Dockerfile
│   └── Dockerfile.cuda     # CUDA-enabled Dockerfile
└── pyproject.toml          # Project configuration
```

## Features

- LLM inference using multiple backends (vLLM, Ollama, llama.cpp)
- Bittensor network integration
- FastAPI-based API endpoints
- Docker support with optional CUDA

## Requirements

- Python 3.12+
- CUDA-capable GPU (optional, for vLLM)
- Bittensor wallet with sufficient stake

## Installation

1. Clone the repository:
```bash
git clone https://github.com/loosh-ai/loosh-inference-miner.git
cd loosh-inference-miner
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```env
NETUID=21
SUBTENSOR_NETWORK=finney
SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443
WALLET_NAME=miner
HOTKEY_NAME=miner
API_HOST=0.0.0.0
API_PORT=8000
AXON_PORT=8089
DEFAULT_MODEL=mistralai/Mistral-7B-v0.1
LLM_BACKEND=llamacpp
TENSOR_PARALLEL_SIZE=1
GPU_MEMORY_UTILIZATION=0.9
MAX_MODEL_LEN=4096
LOG_LEVEL=INFO
```

## Running

### Starting the Miner

```bash
python miner/main.py
```

Or using the provided script:
```bash
./run-miner.sh
```

## Docker Deployment

### Building the Docker Image

```bash
cd docker
docker build -t loosh-inference-miner .
```

### Running with Docker

```bash
docker run -d \
  --name loosh-miner \
  -p 8000:8000 \
  -v ~/.bittensor/wallets:/root/.bittensor/wallets \
  loosh-inference-miner
```

## API Endpoints

- `GET /availability` - Check miner availability
- `POST /inference` - Handle inference requests

## LLM Backends

The miner supports multiple LLM backends:

- **vLLM**: High-performance inference (requires CUDA)
- **Ollama**: Local model serving
- **llama.cpp**: CPU-optimized inference

Select the backend using the `LLM_BACKEND` environment variable.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

