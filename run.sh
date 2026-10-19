#!/usr/bin/env bash
# run.sh — One-command local startup for the ARIA dashboard (development)

set -e
cd "$(dirname "$0")"

# .env is loaded by the app itself (python-dotenv), so values with spaces work.
if [ ! -f .env ]; then
  echo "⚠  No .env file found. Copy .env.example to .env and set DATABASE_URL"
  echo "   (required) plus any API keys you have."
  exit 1
fi

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "✗ Python 3 is not installed. Please install it from https://python.org"
  exit 1
fi

# Create venv if not present
if [ ! -d "venv" ]; then
  echo "✓ Creating virtual environment..."
  python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install / upgrade deps
echo "✓ Installing dependencies..."
pip install -q -r requirements.txt

PORT="${PORT:-8000}"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ARIA — AI Agent Dashboard              ║"
echo "║   http://localhost:${PORT}                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

uvicorn main:app --host 127.0.0.1 --port "$PORT" --reload
