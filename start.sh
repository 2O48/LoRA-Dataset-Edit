#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8100}"
KILL_EXISTING="${KILL_EXISTING:-0}"
export PYTHONUNBUFFERED=1

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
  echo "Install Python 3.11, then run ./start.sh again."
  echo "Ubuntu/Debian example: sudo apt install python3.11 python3.11-venv"
  exit 1
fi

echo "Starting Vision Dataset Studio Web GUI on http://${HOST}:${PORT}"
echo "Local access:  http://127.0.0.1:${PORT}"
echo "LAN access:    use your machine IP with port ${PORT}"

if ! "$PYTHON_CMD" -c "import socket,sys; host=sys.argv[1]; port=int(sys.argv[2]); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((host, port)); s.close()" "$HOST" "$PORT" >/dev/null 2>&1; then
  if [ "$KILL_EXISTING" = "1" ] && command -v fuser >/dev/null 2>&1; then
    echo "Port ${PORT} is already in use. Killing existing process because KILL_EXISTING=1."
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
    sleep 1
    if ! "$PYTHON_CMD" -c "import socket,sys; host=sys.argv[1]; port=int(sys.argv[2]); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((host, port)); s.close()" "$HOST" "$PORT" >/dev/null 2>&1; then
      echo "Port ${PORT} is still unavailable after trying to stop the existing process."
      echo "Use another port: PORT=8101 ./start.sh"
      exit 1
    fi
  else
    echo "Port ${PORT} is already in use."
    echo "Open the existing service at: http://127.0.0.1:${PORT}"
    echo "Or restart by running: KILL_EXISTING=1 ./start.sh"
    echo "Or use another port: PORT=8101 ./start.sh"
    exit 1
  fi
fi

if "$PYTHON_CMD" bootstrap_env.py --is-base-ready >/dev/null 2>&1; then
  echo "[env] Reusing ready project .venv"
else
  if ! "$PYTHON_CMD" bootstrap_env.py --ensure-base; then
    echo "Failed to prepare the local .venv environment."
    exit 1
  fi
fi

VENV_PYTHON="$("$PYTHON_CMD" bootstrap_env.py --print-python)"
exec "$VENV_PYTHON" -u web_server.py --host "$HOST" --port "$PORT"
