#!/bin/bash

# Script to stop the Python AI service

echo "Stopping AI service..."

# Kill all processes using port 9001
lsof -ti:9001 | xargs kill -9 2>/dev/null

# Also kill any uvicorn processes for this app
pkill -f "uvicorn detect_ai:app" 2>/dev/null

sleep 1

# Verify it's stopped
if lsof -ti:9001 > /dev/null 2>&1; then
    echo "Warning: Some processes may still be running. Force killing..."
    lsof -ti:9001 | xargs kill -9 2>/dev/null
    sleep 1
fi

if lsof -ti:9001 > /dev/null 2>&1; then
    echo "ERROR: Could not stop service. Manual intervention needed."
    echo "Run: lsof -ti:9001 | xargs kill -9"
    exit 1
else
    echo "AI service stopped successfully."
fi

