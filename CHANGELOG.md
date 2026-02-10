# Changelog

All notable changes to the Loosh Inference Miner will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-02-09

### Removed

- Removed test mode functionality entirely. The miner no longer supports `TEST_MODE` configuration or fake inference responses. All inference requests now go through the real LLM backend.
  - Removed `test_mode` field from `MinerConfig` in `config.py` and `shared_config.py`
  - Removed `TEST_MODE_PHRASES` and test mode response branch from the inference endpoint
  - Removed `TEST_MODE` environment variable from `env.example`, `PM2/ecosystem.config.js`, and `docker-compose.local-test.yml`

## [0.1.0] - Initial Release

### Added

- Initial miner implementation with FastAPI server
- Support for multiple LLM backends: vLLM, Ollama, llama.cpp
- Fiber MLTS encrypted communication with validators
- Bittensor axon registration and network integration
- OpenAI-compatible message format support
- Tool/function calling support
- Token usage tracking for cost attribution
- PM2 ecosystem configuration for process management
- Docker and RunPod deployment support
- Configurable concurrency limits
