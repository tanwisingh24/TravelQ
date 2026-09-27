#!/bin/bash
# ─────────────────────────────────────────────────────────────
# TravelQ v2 — Start Script (with Auth + Agile)
# ─────────────────────────────────────────────────────────────
echo ""
echo "  ✈️  TravelQ v2 — Travel Budget Planner"
echo "  ──────────────────────────────────────────────────────"
echo ""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "  ❌  Python 3 not found. Install from https://python.org"
    exit 1
fi

# Install Flask if missing
if ! python3 -c "import flask" 2>/dev/null; then
    echo "  📦  Installing Flask..."
    pip3 install flask
fi

# Navigate to backend
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

echo "  🚀  Starting Flask server on http://localhost:5000"
echo "  🔑  Demo account: demo / demo123"
echo "  📋  API Health: http://localhost:5000/api/health"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

python3 app.py
