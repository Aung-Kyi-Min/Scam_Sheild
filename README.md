# Scam Checker - AI-Powered Fraud Detection System

A full-stack application that detects scams in text messages, images, and voice files using AI-powered analysis and rule-based validation.

---

## Overview

**Scam Checker** is a multi-modal fraud detection platform that analyzes suspicious content across three input types:

- **Text**: SMS, emails, chat transcripts
- **Images**: Screenshots, invoices, documents (OCR-based)
- **Voice**: Audio recordings, phone call transcriptions

The system uses a hybrid approach combining **Anthropic Claude AI** for semantic analysis and **rule-based keyword detection** as a fallback, ensuring reliable scam detection even when AI services are unavailable.

---

## Key Features

- **Multi-Modal Detection**: Analyze text, images, and voice files
- **Freemium Model**: Free text checking; image/voice require authentication
- **AI-Powered Analysis**: Claude AI integration with intelligent fallback
- **Real-Time Scoring**: Instant risk assessment (0-100% scale)
- **User Authentication**: Secure signup/login system with session management
- **Advanced Processing**: OCR for images, speech-to-text for audio
- **Responsive UI**: Modern dark-themed interface with real-time feedback
- **Error Handling**: Robust error handling and graceful degradation

---

## Architecture

**Three-Tier Microservices Architecture:**

```
Frontend (Next.js) → Backend (Express.js) → AI Service (FastAPI)
   Port 3000            Port 3001              Port 9001
```

### Components

1. **Frontend**: Next.js 16 with React 19, TypeScript, Tailwind CSS
2. **Backend**: Express.js API gateway with authentication and file handling
3. **AI Service**: FastAPI Python microservice for content analysis

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| **Backend** | Node.js, Express.js 5, Multer, Axios |
| **AI Service** | Python 3, FastAPI, Uvicorn |
| **AI/ML** | Anthropic Claude API, Tesseract OCR, Google Speech Recognition |
| **Authentication** | JWT-like tokens, SHA-256 hashing |
| **Storage** | JSON files (users.json, sessions.json) |
| **IDE** | Cursor (AI-powered code editor) |

---

## Detection Method

### Hybrid Analysis Approach

**Primary**: Anthropic Claude API for semantic understanding
**Fallback**: Rule-based keyword and pattern detection

### Risk Scoring System

```
Risk Score Calculation:
  • High-Risk Keywords: 15 points each (max 80)
  • Medium-Risk Keywords: 5 points each (max 30)
  • Pattern Detection: URLs, phone numbers, money amounts (max 35)
  • Special Pattern Bonuses: Job scams, shortened URLs, urgency tactics
  • File Variation: -3 to +3 based on file hash/size

Risk Levels:
  0-39%  → benign (Safe) 
  40-69% → suspicious (Caution) 
  70-100% → scam (High Risk) 
```

### Detection Patterns

- **Urgency**: "urgent", "verify now", "act immediately"
- **Financial**: "wire transfer", "bitcoin", "send money"
- **Banking**: "account locked", "suspended", "verify account"
- **Shortened URLs**: bit.ly, tinyurl (+50 points - major red flag)
- **Job Scams**: "congrats" + "job" + "payment" (+40 points)
- **Authority Impersonation**: "this is the police", "fbi", "court order"

### Processing Capabilities

**Images**: Multi-strategy OCR with preprocessing (grayscale, contrast, sharpening)
**Voice**: Advanced audio preprocessing with multiple transcription strategies and voice-specific scoring boost (+20%)

---

## Authentication System

**Access Control:**
- **Text checking**: Free, no authentication required
- **Image checking**: Requires user account
- **Voice checking**: Requires user account

**Features:**
- User signup and login
- 30-day session expiration
- Token-based authentication
- Manual login required after signup (no auto-login)

**Storage**: JSON-based (users.json, sessions.json)

---

## Quick Start

### Prerequisites

```bash
# System dependencies
brew install ffmpeg tesseract  # macOS
# or
sudo apt-get install ffmpeg tesseract-ocr  # Linux
```

### Installation

**1. AI Service**
```bash
cd AI
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your_key" > env
uvicorn detect_ai:app --host 127.0.0.1 --port 9001
```

**2. Backend**
```bash
cd backend/scam-checker
npm install
node server.js
```

**3. Frontend**
```bash
cd frontend/scam-checker-ui
npm install
npm run dev
```

**Access**: http://localhost:3000

---

## API Endpoints

### Frontend Routes (Next.js)
- `POST /api/check-scam` - Scam detection proxy
- `POST /api/auth` - Authentication (signup/login/logout/check)
- `GET /api/auth` - Check authentication status

### Backend Routes (Express)
- `POST /api/check` - Main detection endpoint
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User authentication
- `GET /api/auth/check` - Token validation
- `POST /api/auth/logout` - Session termination

### AI Service Routes (FastAPI)
- `POST /predict` - Text/image/voice analysis

**Request Example:**
```json
{
  "text": "URGENT: Verify your account now!",
  "type": "text"
}
```

**Response Example:**
```json
{
  "risk_score": 75,
  "label": "scam",
  "explanation": "HIGH RISK (75%): Multiple scam indicators detected...",
  "recommended_action": "Do not click any links or provide personal information.",
  "input_type": "text"
}
```

---

## Project Structure

```
Event/
├── AI/                          # Python AI Microservice
│   ├── detect_ai.py            # FastAPI app + analysis logic
│   ├── requirements.txt        # Python dependencies
│   └── env                     # API keys (gitignored)
│
├── backend/                     # Node.js API Gateway
│   └── scam-checker/
│       ├── server.js           # Express server
│       ├── users.json          # User storage (gitignored)
│       └── sessions.json       # Session storage (gitignored)
│
└── frontend/                    # Next.js Frontend
    └── scam-checker-ui/
        ├── app/                # Next.js app directory
        │   ├── page.tsx        # Main application
        │   └── api/            # API routes
        └── components/         # React components
            └── AuthModal.tsx   # Authentication modal
```

---

## UI/UX Design

**Theme**: Dark mode with emerald/cyan color palette
**Design Inspiration**: Modern security apps and fintech dashboards
**Features**:
- Color-coded risk visualization (green/yellow/red)
- Real-time validation feedback
- Drag-and-drop file uploads
- Responsive mobile-first design
- Clear error messaging and loading states

---

## Development

**IDE**: Cursor (AI-powered code editor)
- Multi-service workspace management
- AI-assisted debugging and code generation
- Integrated terminal and Git support

**Key Workflows**:
- Hot reload for frontend development
- Error detection and suggestions
- Cross-service code navigation

---

## Production Considerations

**Current (Development)**:
- JSON file storage for users/sessions
- SHA-256 password hashing
- CORS enabled for all origins
- No rate limiting

**Recommended (Production)**:
- Database (PostgreSQL/MongoDB)
- bcrypt for password hashing
- Rate limiting and request throttling
- HTTPS/SSL encryption
- Environment variable management
- Request logging and monitoring
- CSRF protection

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend not responding | Check if services are running on correct ports (3001, 9001) |
| OCR not working | Install Tesseract OCR system package |
| Audio transcription failing | Install ffmpeg, verify file format (MP3/WAV) |
| Authentication errors | Clear localStorage, check backend logs |
| API connection errors | Verify BACKEND_URL and PY_AI_URL environment variables |

---

## License

[Specify license]

---

**Built with using Cursor IDE**

