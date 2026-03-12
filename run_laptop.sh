#!/usr/bin/env bash
# ============================================================================
# PiFace Attendance System - Laptop Development Launcher
# ============================================================================
# Starts all services locally for testing with laptop webcam.
#
# Usage:  ./run_laptop.sh
# Stop:   Press Ctrl+C (kills all background processes)
# ============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
FRONTEND_DIR="$PROJECT_DIR/piface/frontend"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  PiFace Attendance System - Laptop Mode    ${NC}"
echo -e "${CYAN}============================================${NC}"

# --- Check venv ---
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}Virtual environment not found at $VENV_DIR${NC}"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r piface/requirements.txt"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# --- Ensure PYTHONPATH includes project root so 'piface' is importable ---
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# --- Cleanup function ---
PIDS=()
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down all services...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Kill any remaining child processes
    wait 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# --- Start LED Controller (mock mode — no GPIO needed) ---
echo -e "${GREEN}[1/4] Starting LED Controller (mock mode)...${NC}"
python -m piface.core.led_controller > /tmp/piface-led.log 2>&1 &
PIDS+=($!)
sleep 1

# --- Start Face Engine (uses laptop webcam) ---
echo -e "${GREEN}[2/4] Starting Face Engine (webcam)...${NC}"
python -m piface.core.face_engine > /tmp/piface-engine.log 2>&1 &
PIDS+=($!)
sleep 1

# --- Start FastAPI Backend ---
echo -e "${GREEN}[3/4] Starting FastAPI Backend on port 8000...${NC}"
python -m uvicorn piface.backend.main:app --host 127.0.0.1 --port 8000 --reload > /tmp/piface-api.log 2>&1 &
PIDS+=($!)
sleep 1

# --- Start Vite Dev Server (frontend) ---
echo -e "${GREEN}[4/4] Starting Frontend Dev Server on port 5173...${NC}"
cd "$FRONTEND_DIR"
npx vite --host 127.0.0.1 > /tmp/piface-frontend.log 2>&1 &
PIDS+=($!)

sleep 2

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  All services running!                     ${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  ${GREEN}Dashboard:${NC}  http://localhost:5173"
echo -e "  ${GREEN}API:${NC}        http://localhost:8000/docs"
echo -e "  ${GREEN}Login:${NC}      admin / admin"
echo ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    LED Controller: /tmp/piface-led.log"
echo -e "    Face Engine:    /tmp/piface-engine.log"
echo -e "    API Server:     /tmp/piface-api.log"
echo -e "    Frontend:       /tmp/piface-frontend.log"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for any process to exit
wait
