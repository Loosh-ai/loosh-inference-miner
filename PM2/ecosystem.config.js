/**
 * PM2 Ecosystem Configuration for Loosh Inference Miner
 * 
 * This configuration automatically loads settings from .env file and creates
 * appropriate PM2 apps based on the LLM_BACKEND setting:
 * 
 * - vllm: Creates two apps - vLLM server and miner (vLLM server starts first)
 * - ollama: Creates only miner app (assumes Ollama is running as system service)
 * - llamacpp: Creates only miner app (runs in-process)
 * 
 * Usage:
 *   pm2 start PM2/ecosystem.config.js
 *   pm2 logs loosh-inference-miner
 *   pm2 logs loosh-vllm-server  # (if using vLLM backend)
 */

// Load .env file if it exists
const fs = require('fs');
const path = require('path');

function loadEnvFile() {
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    envContent.split('\n').forEach(line => {
      const trimmedLine = line.trim();
      if (trimmedLine && !trimmedLine.startsWith('#')) {
        const [key, ...valueParts] = trimmedLine.split('=');
        if (key && valueParts.length > 0) {
          const value = valueParts.join('=').replace(/^["']|["']$/g, '');
          if (!process.env[key]) {
            process.env[key] = value;
          }
        }
      }
    });
  }
}

// Load environment variables from .env
loadEnvFile();

// Get configuration with defaults
const LLM_BACKEND = process.env.LLM_BACKEND || 'llamacpp';
const API_HOST = process.env.API_HOST || '0.0.0.0';
const API_PORT = process.env.API_PORT || '8000';
const DEFAULT_MODEL = process.env.DEFAULT_MODEL || 'mistralai/Mistral-7B-v0.1';
const VLLM_API_BASE = process.env.VLLM_API_BASE || 'http://localhost:8000/v1';
const TENSOR_PARALLEL_SIZE = process.env.TENSOR_PARALLEL_SIZE || '1';
const GPU_MEMORY_UTILIZATION = process.env.GPU_MEMORY_UTILIZATION || '0.9';
const MAX_MODEL_LEN = process.env.MAX_MODEL_LEN || '4096';
const WORKDIR = process.env.MINER_WORKDIR || process.cwd();

// Extract vLLM port from VLLM_API_BASE
let VLLM_PORT = '8000';
const vllmPortMatch = VLLM_API_BASE.match(/:(\d+)/);
if (vllmPortMatch) {
  VLLM_PORT = vllmPortMatch[1];
}

// Base configuration for all apps
const baseConfig = {
  cwd: WORKDIR,
  watch: false,
  autorestart: true,
  max_restarts: 10,
  min_uptime: '10s',
  time: true,
  merge_logs: true,
  log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
  env: {
    PYTHONPATH: WORKDIR,
    PYTHONUNBUFFERED: '1',
    NODE_ENV: 'production',
  }
};

// Build apps array based on backend
const apps = [];

// If vLLM backend, add vLLM server app
if (LLM_BACKEND === 'vllm') {
  apps.push({
    ...baseConfig,
    name: 'loosh-vllm-server',
    script: 'python',
    args: [
      '-m', 'vllm.entrypoints.openai.api_server',
      '--model', DEFAULT_MODEL,
      '--tensor-parallel-size', TENSOR_PARALLEL_SIZE,
      '--gpu-memory-utilization', GPU_MEMORY_UTILIZATION,
      '--max-model-len', MAX_MODEL_LEN,
      '--port', VLLM_PORT
    ].join(' '),
    interpreter: process.env.PYTHON_INTERPRETER || 'python3',
    max_memory_restart: '16G', // vLLM can use more memory
    error_file: './logs/vllm-error.log',
    out_file: './logs/vllm-out.log',
    log_file: './logs/vllm-combined.log',
    kill_timeout: 30000,
    // vLLM can take a while to download and load models
    min_uptime: '30s', // Give vLLM more time before considering it stable
    env: {
      ...baseConfig.env,
      DEFAULT_MODEL: DEFAULT_MODEL,
      TENSOR_PARALLEL_SIZE: TENSOR_PARALLEL_SIZE,
      GPU_MEMORY_UTILIZATION: GPU_MEMORY_UTILIZATION,
      MAX_MODEL_LEN: MAX_MODEL_LEN,
    }
  });
}

// Miner app (always included)
apps.push({
  ...baseConfig,
  name: 'loosh-inference-miner',
  script: 'uvicorn',
  args: `miner.miner_server:app --host ${API_HOST} --port ${API_PORT}`,
  interpreter: process.env.PYTHON_INTERPRETER || 'python3',
  max_memory_restart: '8G',
  error_file: './logs/miner-error.log',
  out_file: './logs/miner-out.log',
  log_file: './logs/miner-combined.log',
  // If vLLM is used, give it time to start before the miner
  ...(LLM_BACKEND === 'vllm' ? {
    instances: 1,
    // Miner will retry connection to vLLM if it's not ready yet
    min_uptime: '20s',
  } : {}),
  env: {
    ...baseConfig.env,
    LLM_BACKEND: LLM_BACKEND,
    API_HOST: API_HOST,
    API_PORT: API_PORT,
    DEFAULT_MODEL: DEFAULT_MODEL,
    VLLM_API_BASE: VLLM_API_BASE,
    OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://localhost:11434',
    OLLAMA_TIMEOUT: process.env.OLLAMA_TIMEOUT || '300.0',
    MODEL_PATH: process.env.MODEL_PATH || '',
    TENSOR_PARALLEL_SIZE: TENSOR_PARALLEL_SIZE,
    GPU_MEMORY_UTILIZATION: GPU_MEMORY_UTILIZATION,
    MAX_MODEL_LEN: MAX_MODEL_LEN,
    // Include all other env vars that might be needed
    NETUID: process.env.NETUID || '',
    SUBTENSOR_NETWORK: process.env.SUBTENSOR_NETWORK || '',
    SUBTENSOR_ADDRESS: process.env.SUBTENSOR_ADDRESS || '',
    WALLET_NAME: process.env.WALLET_NAME || '',
    HOTKEY_NAME: process.env.HOTKEY_NAME || '',
    LOG_LEVEL: process.env.LOG_LEVEL || 'INFO',
    TEST_MODE: process.env.TEST_MODE || 'false',
    FIBER_KEY_TTL_SECONDS: process.env.FIBER_KEY_TTL_SECONDS || '3600',
    FIBER_HANDSHAKE_TIMEOUT_SECONDS: process.env.FIBER_HANDSHAKE_TIMEOUT_SECONDS || '30',
    FIBER_ENABLE_KEY_ROTATION: process.env.FIBER_ENABLE_KEY_ROTATION || 'true',
    MAX_CONCURRENT_REQUESTS: process.env.MAX_CONCURRENT_REQUESTS || '10',
  }
});

module.exports = {
  apps: apps
};

