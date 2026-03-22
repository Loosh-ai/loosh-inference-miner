# Changelog

All notable changes to the Loosh Inference Miner will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.2] - 2026-03-18

### Added

- **DDoS mitigation: sr25519 signature verification** — The miner now verifies the validator's sr25519 signature during Fiber key exchange (`{timestamp}.{nonce}.{validator_hotkey_ss58}`) **before** performing the expensive RSA decryption step. Requests with invalid or missing signatures are rejected immediately (`miner/network/fiber_server.py`).
- **DDoS mitigation: validator hotkey whitelist** — When `ENABLE_VALIDATOR_WHITELIST=true` (default), the miner maintains a set of known validator hotkeys sourced from the Bittensor metagraph (nodes with `validator_permit=True`) and optionally from the Challenge API (`GET /validators/active-hotkeys`). Requests from unknown hotkeys are rejected with 403 before any crypto work or inference. During bootstrap (before first metagraph sync), all hotkeys are temporarily allowed (`miner/network/validator_whitelist.py`).
- **DDoS mitigation: IP-aware rate limiting** — New middleware enforces fixed-window rate limits per source IP and per claimed validator hotkey. Known validator IPs (resolved from the Challenge API) receive relaxed limits (e.g. `/fiber/challenge` 120/min), while unknown IPs receive strict thresholds (e.g. `/fiber/challenge` 30/min). Per-hotkey limit is 60/min across all endpoints. Exceeding the limit returns 429 with `Retry-After` header (`miner/middleware/rate_limiter.py`).
- **Validator IP tracking** — The `ValidatorWhitelist` now extracts and stores the `ip` field from the Challenge API's `/validators/active-hotkeys` response and exposes it to the rate limiter via the `validator_ips` property (`miner/network/validator_whitelist.py`).
- **Hotkey signature auth for Challenge API polling** — The miner now authenticates to the Challenge API's `/validators/active-hotkeys` endpoint using sr25519 hotkey signatures (`X-Hotkey`, `X-Nonce`, `X-Signature` headers), mirroring the existing validator-to-Challenge-API authentication scheme. Falls back to `X-API-Key` for backward compatibility with older Challenge API deployments (`miner/network/challenge_api_auth.py`).
- **Security documentation** — Added `docs/MINER_SECURITY.md` covering all application-level protections, recommended infrastructure defences (reverse proxy, firewall rules, cloud DDoS protection), and an attack scenario/mitigation matrix.
- **Automated firewall management guide** — Added `docs/AUTOMATED_FIREWALL.md` with production-ready scripts for UFW, iptables, and nftables that dynamically restrict miner port access to active validator IPs using the Challenge API's authenticated endpoint. Includes Docker, systemd timer, and cron scheduling examples.

### Changed

- **Compute requirements: removed RTX 5080 / 16 GB VRAM tier** — The `rtx_5080_16gb` GPU profile and its associated model allowlist (Phi-3.5-mini, Qwen2.5-7B, Llama-3.1-8B) have been removed from `min_compute.yml`. The minimum GPU tier is now the A10 24 GB.
- **Default model upgraded to Qwen2.5-14B-Instruct** — `DEFAULT_MODEL` changed from `mistralai/Mistral-7B-v0.1` to `Qwen/Qwen2.5-14B-Instruct` in `env.example` and the default config, reflecting the higher-quality model required for current evaluation criteria.
- **Default max tokens increased to 12288** — `DEFAULT_MAX_TOKENS` raised from 512 to 12288 in `env.example` to support the longer completions expected by the evaluation pipeline.
- **Default LLM backend changed to vLLM** — `LLM_BACKEND` default changed from `llamacpp` to `vllm` in `env.example`, aligning with the recommended production deployment.
- **Uvicorn connection limits** — The Docker/supervisord deployment now configures `--timeout-keep-alive 5`, `--limit-concurrency 50`, and `--limit-max-requests 10000` on the uvicorn command line. Overridable via `UVICORN_KEEP_ALIVE`, `UVICORN_LIMIT_CONCURRENCY`, `UVICORN_LIMIT_MAX_REQUESTS` environment variables (`docker/supervisord.conf`).

### Deprecated

- **`CHALLENGE_API_KEY`** — The miner now authenticates with the Challenge API using its sr25519 hotkey. The `challenge_api_key` config field is retained for backward compatibility but will be removed in a future release.

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
