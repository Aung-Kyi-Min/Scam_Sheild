# utils_processing.py
import os
import re
import json
import base64
import requests
from fastapi import HTTPException

# Optional OCR and audio modules
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import speech_recognition as sr
    from pydub import AudioSegment
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False


def call_claude_classify(text: str):
    """Send text to Claude for scam classification."""
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Missing ANTHROPIC_API_KEY")

    prompt = f"""
You are a scam detection AI. Analyze the message and return:

{{
  "risk_score": <0-100>,
  "label": "benign" | "suspicious" | "scam",
  "explanation": "...",
  "recommended_action": "..."
}}

Message:
{text}
"""

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}]
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    data = resp.json()

    try:
        content = data["content"][0]["text"]
        return json.loads(content)
    except:
        # Late import to avoid circular dependency
        from AI.detect_ai import simple_keyword_score
        return {
            "risk_score": simple_keyword_score(text),
            "label": "suspicious",
            "explanation": "Claude response unreadable, fallback used.",
            "recommended_action": "Be cautious."
        }


def generate_elevenlabs_audio_base64(text: str):
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    if not ELEVENLABS_API_KEY:
        return None

    url = "https://api.elevenlabs.io/v1/text-to-speech/YOUR_VOICE_ID"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {"text": text}
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        return None

    return base64.b64encode(resp.content).decode()


def extract_text_from_image(path: str) -> str:
    if not OCR_AVAILABLE:
        return "OCR not available."

    try:
        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception as e:
        return f"OCR error: {e}"

def transcribe_audio(path: str) -> str:
    if not AUDIO_AVAILABLE:
        return "Audio transcription not available."

    try:
        audio = AudioSegment.from_file(path)
        wav_path = path.replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")

        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = r.record(source)
            return r.recognize_google(audio_data)

    except Exception as e:
        return f"Transcription error: {e}"

def analyze_text(text: str):
    """Analyze text for scam indicators."""
    # Late import to avoid circular dependency
    from AI.detect_ai import simple_keyword_score
    
    if len(text) == 0:
        raise HTTPException(status_code=400, detail="text empty")

    # 1) Try to call Claude, fall back to improved keyword detection
    try:
        claude_out = call_claude_classify(text)
        # Expect keys risk_score,label,explanation,recommended_action
        risk = int(claude_out.get("risk_score", simple_keyword_score(text)))
        label = claude_out.get("label", "suspicious")
        explanation = claude_out.get("explanation", "")
        recommended_action = claude_out.get("recommended_action", "")
    except Exception as e:
        # fallback - use improved keyword detection
        error_str = str(e)
        risk = simple_keyword_score(text)
        
        # Determine label based on risk score
        if risk >= 70:
            label = "scam"
        elif risk >= 40:
            label = "suspicious"
        else:
            label = "benign"
        
        # Generate dynamic explanation based on risk
        if risk >= 70:
            explanation = f"⚠️ HIGH RISK ({risk}%): Multiple scam indicators detected including urgent language, suspicious links, or financial requests. This appears to be a scam."
            recommended_action = "DO NOT respond, click links, or provide any information. Delete this message and block the sender."
        elif risk >= 40:
            explanation = f"⚠️ MODERATE RISK ({risk}%): Some suspicious elements detected. Exercise caution with this message."
            recommended_action = "Verify the sender through a known, trusted channel before taking any action. Do not click links or provide personal information."
        elif risk >= 20:
            explanation = f"⚠️ LOW RISK ({risk}%): Minor suspicious elements detected. Proceed with caution."
            recommended_action = "Verify the sender's identity before responding or clicking any links."
        else:
            explanation = f"✅ LOW RISK ({risk}%): No significant scam indicators detected. This message appears safe."
            recommended_action = "This message appears legitimate, but always verify independently when in doubt."

    result = {
        "risk_score": risk,
        "label": label,
        "explanation": explanation,
        "recommended_action": recommended_action
    }

    # Optionally produce voice warning for high risks
    if risk >= 60:
        voice_text = f"Warning. This message appears to be a scam. Risk score {risk} percent. {explanation}"
        audio_b64 = generate_elevenlabs_audio_base64(voice_text)
        if audio_b64:
            result["audio_base64"] = audio_b64

    return result
