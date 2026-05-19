#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
exec conda run --no-capture-output -n caption-codex python -u web_server.py --host 127.0.0.1 --port 8100
