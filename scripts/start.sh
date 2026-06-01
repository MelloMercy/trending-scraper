#!/usr/bin/env bash
# Start the trending-scraper web service on port 11001.
#
# Usage:
#   bash /Users/mercy/projects/auto\ scripts/trending-scraper/scripts/start.sh
#   bash scripts/start.sh                  # if already in project dir
#   ./scripts/start.sh                     # if marked executable
#
# Behavior:
#   - Always cd into the project root (resolved from $0), so it works from
#     anywhere
#   - Activates the venv at .venv/
#   - Kills any existing process on :11001 before starting (matches the
#     trending123 zsh function — D021 / D023 contract)
#   - Foreground uvicorn → Ctrl+C to stop
#
# Env vars:
#   PORT          override port (default 11001)
#   RELOAD=1      run uvicorn with --reload (dev mode, autoreload on save)

set -euo pipefail

# Resolve project root from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PORT="${PORT:-11001}"

cd "$PROJECT_DIR"

# Verify venv
if [ ! -d ".venv" ]; then
  echo "✗ .venv not found at $PROJECT_DIR/.venv"
  echo "  Bootstrap with:"
  echo "    python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

# Self-clean any process on the target port
PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "↻ cleaning up existing PID(s) on :$PORT — $PIDS"
  echo "$PIDS" | xargs kill 2>/dev/null || true
  sleep 0.5
fi

# Start
RELOAD_FLAG=""
if [ "${RELOAD:-0}" = "1" ]; then
  RELOAD_FLAG="--reload"
  echo "🔄 dev mode (--reload)"
fi

echo "🚀 starting uvicorn on http://localhost:$PORT"
exec uvicorn main:app --port "$PORT" $RELOAD_FLAG
