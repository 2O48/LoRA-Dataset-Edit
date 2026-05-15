#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec conda run -n caption-codex python lora_reviewer.py
