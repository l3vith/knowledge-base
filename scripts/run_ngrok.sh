#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-}"
ENV_FILE="${KB_ENV_FILE:-$ROOT/.env}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    VENV_PYTHON_VERSION="$("$ROOT/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    if [[ "$VENV_PYTHON_VERSION" == "3.12" ]]; then
      PYTHON_BIN="$ROOT/.venv/bin/python"
    fi
  fi
  if [[ -z "$PYTHON_BIN" ]] && command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  elif [[ -z "$PYTHON_BIN" ]]; then
    echo "Python 3.12 is required. Create the project environment with: python3.12 -m venv .venv" >&2
    exit 1
  fi
fi

if ! "$PYTHON_BIN" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "FastAPI dependencies are missing for $PYTHON_BIN. Install them with: $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi
PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
  echo "Python 3.12 is required by this project; $PYTHON_BIN is Python $PYTHON_VERSION." >&2
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok is not installed. Install it with: brew install ngrok/ngrok/ngrok" >&2
  exit 1
fi

if ! ngrok config check >/dev/null 2>&1; then
  echo "ngrok is not configured. Add your account token with: ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>" >&2
  exit 1
fi

cd "$ROOT"
"$PYTHON_BIN" -m scripts.serve --env-file "$ENV_FILE" --host 127.0.0.1 --port "$PORT" &
API_PID=$!
cleanup() {
  kill "$API_PID" >/dev/null 2>&1 || true
  wait "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for _ in $(seq 1 60); do
  if ! kill -0 "$API_PID" >/dev/null 2>&1; then
    echo "API server exited before becoming ready." >&2
    exit 1
  fi
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X GET "http://127.0.0.1:$PORT/query" || true)"
  if [[ "$code" =~ ^[234] ]]; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  echo "API did not become ready on port $PORT." >&2
  exit 1
fi

echo "API is ready on http://127.0.0.1:$PORT; starting the public tunnel."
ngrok http "$PORT"
