# Changelog

All notable changes to the Loosh Inference Miner will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-02-12

### Fixed

- **Fiber MLTS key recovery after miner restart** — When a miner restarts, its in-memory symmetric key cache is wiped. Previously, the miner returned `400 Bad Request` for challenges encrypted with stale keys, which validators did not recognise as a signal to re-handshake. The miner now returns `401 Unauthorized` with its current RSA public key embedded in the response body (`requires_handshake: true`, `public_key: <PEM>`). Validators that receive this response can re-handshake in a single round-trip (inline re-negotiation) instead of the usual two-step GET public-key → POST key-exchange flow. Fully backward-compatible — old validators that only check for 401 without parsing the body will still re-handshake via the standard flow (`miner/endpoints/fiber.py`).

### Added

- **Backend readiness gate** — The miner now polls the LLM backend's health endpoint on startup and returns `503 Service Unavailable` for challenge requests until the backend reports healthy. This prevents validators from receiving errors (and penalising the miner) while the LLM backend (e.g. vLLM) is still loading the model. Polls every 5 seconds with periodic log updates (`miner/miner_server.py`).

### Changed

- **Config singleton** — `get_config()` now caches the `MinerConfig` instance after first creation instead of re-creating it on every HTTP request. This eliminates the per-request "Loaded configuration" log spam that obscured useful log output (`miner/dependencies.py`).

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
