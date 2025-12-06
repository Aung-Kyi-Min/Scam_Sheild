#!/bin/bash

# Script to start the Python AI service
# This script will kill any existing process on port 9001 and start a fresh one

cd "$(dirname "$0")"

echo "Stopping any existing AI service on port 9001..."

# Kill all processes using port 9001
lsof -ti:9001 | xargs kill -9 2>/dev/null

# Also kill any uvicorn processes for this app
pkill -f "uvicorn.*detect_ai:app" 2>/dev/null

# Wait a moment for ports to be released
sleep 2

# Check if port is still in use
if lsof -ti:9001 > /dev/null 2>&1; then
    echo "Warning: Port 9001 is still in use. Trying to force kill..."
    lsof -ti:9001 | xargs kill -9 2>/dev/null
    sleep 2
fi

# Verify port is free
if lsof -ti:9001 > /dev/null 2>&1; then
    echo "ERROR: Port 9001 is still in use. Please manually kill the process:"
    echo "  lsof -ti:9001 | xargs kill -9"
    exit 1
fi

echo "Starting AI service on port 9001..."
# Run from parent directory so AI package imports work correctly
cd "$(dirname "$0")/.."
uvicorn AI.detect_ai:app --host 127.0.0.1 --port 9001

