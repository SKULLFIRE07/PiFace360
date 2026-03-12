#!/usr/bin/env bash
# ============================================================
# PiFace Attendance System — Local Laptop Launcher
# Starts: Backend API + Face Engine + Frontend Dev Server
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_DIR/venv"

if [ ! -d "$VENV" ]; then
    echo "ERROR: Virtual environment not found at $VENV"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r piface/requirements.txt"
    exit 1
fi

# Activate venv
source "$VENV/bin/activate"

# Ensure PYTHONPATH includes project root so "piface.*" imports work
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down all services..."
    kill $PID_ENGINE $PID_BACKEND $PID_FRONTEND 2>/dev/null
    wait $PID_ENGINE $PID_BACKEND $PID_FRONTEND 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

echo "=========================================="
echo "  PiFace Attendance — Local Laptop Mode"
echo "=========================================="
echo ""

# 1. Start Face Engine (background)
echo "[1/3] Starting Face Engine..."
python -m piface.core.face_engine &
PID_ENGINE=$!
echo "       PID=$PID_ENGINE"

# 2. Start Backend API (background)
echo "[2/3] Starting Backend API on http://localhost:8001 ..."
python -m uvicorn piface.backend.main:app --host 127.0.0.1 --port 8001 --reload &
PID_BACKEND=$!
echo "       PID=$PID_BACKEND"

# 3. Start Frontend Dev Server (background)
echo "[3/3] Starting Frontend on http://localhost:5173 ..."
cd "$PROJECT_DIR/piface/frontend"
npm run dev &
PID_FRONTEND=$!
echo "       PID=$PID_FRONTEND"
cd "$PROJECT_DIR"

echo ""
echo "=========================================="
echo "  All services running!"
echo ""
echo "  Frontend:  http://localhost:5173"
echo "  Backend:   http://localhost:8001"
echo "  Login:     admin / admin"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "=========================================="

# Wait for any process to exit
wait
