#!/bin/bash

# Heckler startup script
# Starts backend, frontend, and launches Chromium browser

set -e

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Heckler...${NC}"

# Cleanup function to kill background processes on exit
cleanup() {
    echo -e "\n${RED}Shutting down...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}Starting backend server...${NC}"
cd backend
source .venv/bin/activate
uv run python -m heckler.app &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 2

# Start frontend
echo -e "${GREEN}Starting frontend dev server...${NC}"
cd frontend
pnpm dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend to be ready
echo "Waiting for frontend to start..."
sleep 3

# Launch Chromium
echo -e "${GREEN}Launching Chromium...${NC}"
chromium-browser --app=http://localhost:5173 &

echo -e "${BLUE}Heckler is running!${NC}"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop all services"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
