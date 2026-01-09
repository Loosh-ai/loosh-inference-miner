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
├── PM2/                     # PM2 process manager configuration
│   └── ecosystem.config.js # PM2 ecosystem configuration
└── pyproject.toml          # Project configuration
```

## Features

- LLM inference using multiple backends (vLLM, Ollama, llama.cpp)
- Bittensor network integration
- FastAPI-based API endpoints
- Docker support with optional CUDA

## Requirements

- Python 3.12+
- uv (Python package installer) - [Installation instructions](https://github.com/astral-sh/uv)
- CUDA-capable GPU (optional, for vLLM)
- Bittensor wallet with sufficient stake

## Installation

1. Clone the repository:
```bash
git clone https://github.com/loosh-ai/loosh-inference-miner.git
cd loosh-inference-miner
```

2. Install uv (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

3. Install dependencies:
```bash
uv sync
```

This will automatically create a virtual environment and install all dependencies from `pyproject.toml`.

To activate the virtual environment:
```bash
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
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

### PM2 Deployment

PM2 is a process manager for Node.js applications that can also manage Python applications. It provides automatic restarts, logging, and monitoring capabilities.

#### Prerequisites

Install PM2 globally:
```bash
npm install -g pm2
```

#### Starting with PM2

1. Ensure you have a `.env` file configured (see Configuration section above)

2. Create the logs directory:
```bash
mkdir -p logs
```

3. Start the miner using PM2:
```bash
pm2 start PM2/ecosystem.config.js
```

#### PM2 Management Commands

- **View status**: `pm2 status`
- **View logs**: `pm2 logs loosh-inference-miner`
- **Stop miner**: `pm2 stop loosh-inference-miner`
- **Restart miner**: `pm2 restart loosh-inference-miner`
- **Delete from PM2**: `pm2 delete loosh-inference-miner`
- **Monitor**: `pm2 monit`
- **Save PM2 process list**: `pm2 save`
- **Setup PM2 to start on system boot**: `pm2 startup`

#### Configuration

The PM2 configuration file is located at `PM2/ecosystem.config.js`. You can customize:

- `MINER_WORKDIR`: Working directory (defaults to current directory)
- `PYTHON_INTERPRETER`: Python interpreter path (defaults to `python3`)
- `max_memory_restart`: Maximum memory before restart (default: 8G)
- Log file paths and other PM2 options

#### Environment Variables

You can override PM2 configuration using environment variables:

```bash
MINER_WORKDIR=/path/to/miner PYTHON_INTERPRETER=python3.12 pm2 start PM2/ecosystem.config.js
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

