module.exports = {
  apps: [
    {
      name: 'loosh-inference-miner',
      script: 'uvicorn',
      args: `miner.miner_server:app --host ${process.env.API_HOST || '0.0.0.0'} --port ${process.env.API_PORT || '8000'}`,
      interpreter: process.env.PYTHON_INTERPRETER || 'python3',
      cwd: process.env.MINER_WORKDIR || process.cwd(),
      watch: false,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      max_memory_restart: '8G',
      env: {
        PYTHONPATH: process.env.MINER_WORKDIR || process.cwd(),
        PYTHONUNBUFFERED: '1',
        NODE_ENV: 'production',
        API_HOST: process.env.API_HOST || '0.0.0.0',
        API_PORT: process.env.API_PORT || '8000'
      },
      error_file: './logs/miner-error.log',
      out_file: './logs/miner-out.log',
      log_file: './logs/miner-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};

