#!/bin/bash
# Run miner using uvicorn
PYTHONPATH=. uv run uvicorn miner.miner_server:app --host 0.0.0.0 --port 8100 --reload

