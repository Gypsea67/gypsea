#!/bin/bash
# Gypsea Orchestrator — one-time setup
set -e

GYPSEA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "[Gypsea] Installing from $GYPSEA_DIR"

# Python venv + deps
echo "[Gypsea] Setting up Python venv..."
cd "$GYPSEA_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Node deps
echo "[Gypsea] Installing frontend dependencies..."
cd "$GYPSEA_DIR/frontend"
npm install

# Verify symlink
if [ -L "$GYPSEA_DIR/storage" ]; then
    echo "[Gypsea] Storage symlink OK: $(readlink "$GYPSEA_DIR/storage")"
else
    echo "[Gypsea] WARNING: storage symlink missing. Create it:"
    echo "  ln -sf /mnt/d/Bloknot/Reels/Work/Projects/gypseaorchestrator $GYPSEA_DIR/storage"
fi

echo "[Gypsea] Install complete. Run: ./scripts/run.sh"
