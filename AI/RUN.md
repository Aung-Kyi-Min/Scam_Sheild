# How to Run the Python AI Service

## Quick Start

### Option 1: Use Helper Scripts (Recommended - No Port Conflicts!)

**Start the service:**
```bash
cd "simple-scam-checker copy/backend/ai-testing"
./start.sh
```

**Stop the service:**
```bash
cd "simple-scam-checker copy/backend/ai-testing"
./stop.sh
```

The `start.sh` script automatically kills any existing process on port 9001 before starting, so you'll never get "address already in use" errors!

### Option 2: Manual Commands

### 1. Navigate to the AI directory
```bash
cd "simple-scam-checker copy/backend/ai-testing"
```

### 2. Install system dependencies (first time only)

**Install ffmpeg (required for audio processing):**
```bash
# On macOS (using Homebrew):
brew install ffmpeg

# On Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y ffmpeg

# On other systems, see: https://ffmpeg.org/download.html
```

**Install Python dependencies:**
```bash
pip install -r requirements.txt
```

### 3. Stop any existing service first
```bash
# Kill any process on port 9001
lsof -ti:9001 | xargs kill -9 2>/dev/null
pkill -f "uvicorn ai:app" 2>/dev/null
sleep 2
```

### 4. Run the service
```bash
uvicorn ai:app --host 127.0.0.1 --port 9001
```

## Full Command Breakdown

```bash
uvicorn ai:app --host 127.0.0.1 --port 9001
```

- `uvicorn` - ASGI server for FastAPI
- `ai:app` - The module name (`ai.py`) and app instance (`app`)
- `--host 127.0.0.1` - Listen on localhost only
- `--port 9001` - Use port 9001 (changed from 9000 to avoid PHP-FPM conflict)

## Alternative: Run in Background

### Using nohup (keeps running after terminal closes)
```bash
cd "simple-scam-checker copy/backend/ai-testing"
nohup uvicorn ai:app --host 127.0.0.1 --port 9001 > /tmp/uvicorn.log 2>&1 &
```

### Check if it's running
```bash
ps aux | grep "uvicorn ai:app" | grep -v grep
```

### View logs
```bash
tail -f /tmp/uvicorn.log
```

### Stop the service
```bash
pkill -f "uvicorn ai:app"
```

## Using Different Ports

If port 9001 is in use, you can use a different port:

```bash
uvicorn ai:app --host 127.0.0.1 --port 9002
```

**Important**: If you change the port, also update `backend/server.js`:
```javascript
const PY_AI_URL = process.env.PY_AI_URL || "http://127.0.0.1:9002";
```

## Development Mode (Auto-reload on changes)

```bash
uvicorn ai:app --host 127.0.0.1 --port 9001 --reload
```

## Verify It's Working

### Check the API docs
Open in browser: http://127.0.0.1:9001/docs

### Test with curl
```bash
curl -X POST http://127.0.0.1:9001/predict \
  -F "text=URGENT: Verify your account!" \
  -F "type=text"
```

### Expected output
```json
{
  "risk_score": 42,
  "label": "suspicious",
  "explanation": "⚠️ MODERATE RISK (42%): Some suspicious elements detected...",
  "recommended_action": "Verify the sender through a known, trusted channel...",
  "input_type": "text"
}
```

## Troubleshooting

### Port already in use (EADDRINUSE error)

**Easiest solution - Use the helper script:**
```bash
cd "simple-scam-checker copy/backend/ai-testing"
./start.sh
```

**Manual solution:**
```bash
# Find and kill all processes using port 9001
lsof -ti:9001 | xargs kill -9 2>/dev/null

# Also kill any uvicorn processes
pkill -f "uvicorn ai:app" 2>/dev/null

# Wait a moment
sleep 2

# Verify port is free
lsof -ti:9001

# If nothing is returned, port is free. Start the service:
uvicorn ai:app --host 127.0.0.1 --port 9001
```

**One-liner to kill and restart:**
```bash
cd "simple-scam-checker copy/backend/ai-testing" && lsof -ti:9001 | xargs kill -9 2>/dev/null; pkill -f "uvicorn ai:app" 2>/dev/null; sleep 2 && uvicorn ai:app --host 127.0.0.1 --port 9001
```

### Module not found errors
```bash
# Make sure you're in the right directory
cd "simple-scam-checker copy/backend/ai-testing"

# Reinstall dependencies
pip install -r requirements.txt
```

### Permission errors
```bash
# Use python3 explicitly if needed
python3 -m uvicorn ai:app --host 127.0.0.1 --port 9001
```

## Environment Variables (Optional)

Create a `.env` file in the `ai-testing` directory:

```bash
cd "simple-scam-checker copy/backend/ai-testing"
nano .env
```

Add:
```
ANTHROPIC_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here
```

The service will work without these (uses fallback keyword detection).

