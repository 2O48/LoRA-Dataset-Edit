#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec conda run -n caption-codex python web_server.py --host 127.0.0.1 --port 8100
