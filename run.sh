#!/usr/bin/env bash
# run.sh — One-command startup for the ARIA dashboard

set -e

# Load .env if it exists
if [ -f .env ]; then
  echo "✓ Loading environment variables from .env"
  export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
  echo "⚠  No .env file found. Copy .env.example to .env and fill in your API keys."
  echo "   Some widgets may not work without API keys."
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

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ARIA — AI Agent Dashboard              ║"
echo "║   http://localhost:8000                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
