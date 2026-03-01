#!/bin/bash
# Gypsea Orchestrator — start backend + frontend
set -e

GYPSEA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$GYPSEA_DIR"

# Activate venv
source .venv/bin/activate 2>/dev/null || {
    echo "[Gypsea] No venv found. Run ./scripts/install.sh first."
    exit 1
}

echo "[Gypsea] Starting backend on :8765..."
python -m uvicorn backend.main:app --port 8765 --reload &
BACKEND_PID=$!

echo "[Gypsea] Starting frontend on :5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

cd "$GYPSEA_DIR"

echo "[Gypsea] Starting ChatClaw on :3000..."
cd chatclaw && npx next dev --port 3000 &
CHATCLAW_PID=$!

cd "$GYPSEA_DIR"

trap "kill $BACKEND_PID $FRONTEND_PID $CHATCLAW_PID 2>/dev/null; exit" INT TERM

echo ""
echo "[Gypsea] Running!"
echo "  Backend:   http://localhost:8765"
echo "  Frontend:  http://localhost:5173"
echo "  ChatClaw:  http://localhost:3000"
echo "  API docs:  http://localhost:8765/docs"
echo ""
echo "Press Ctrl+C to stop."

wait
