#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

WITH_QWEN=0
if [[ "${1:-}" == "--with-qwen" ]]; then
  WITH_QWEN=1
fi

find_python() {
  if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    echo "$PYTHON"
    return 0
  fi
  for candidate in python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_CMD="$(find_python || true)"
if [ -z "$PYTHON_CMD" ]; then
  echo "Python was not found."
  echo "Install Python 3.11, then run ./install.sh again."
  echo "Ubuntu/Debian example: sudo apt install python3.11 python3.11-venv"
  exit 1
fi

echo "Preparing project virtual environment for Vision Dataset Studio..."
if [ "$WITH_QWEN" = "1" ]; then
  "$PYTHON_CMD" bootstrap_env.py --ensure-qwen
else
  "$PYTHON_CMD" bootstrap_env.py --ensure-base
fi

echo
echo "Environment ready."
echo "Project Python: $("$PYTHON_CMD" bootstrap_env.py --print-python)"
echo "Next step: ./start.sh"
