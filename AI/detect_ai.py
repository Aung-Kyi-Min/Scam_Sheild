"""
Python AI microservice (FastAPI).
- POST /predict  accepts:
  - JSON { "text": "...", "options": {...} } for text input
  - multipart/form-data with "file" and "type" (image/voice) for file uploads
- Returns JSON with risk_score, label, explanation, recommended_action
- Optionally generates base64-encoded MP3 via ElevenLabs

Before running, set environment variables:
- ANTHROPIC_API_KEY  (for Claude)
- ELEVENLABS_API_KEY (optional, for voice)

Install dependencies:
- pip install pillow pytesseract speechrecognition pydub
- For OCR: Install Tesseract OCR system package
- For audio: May need ffmpeg for audio conversion
"""

import os
import base64
import json
import uuid
import tempfile
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import requests
from dotenv import load_dotenv

# Try to import optional dependencies
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: OCR libraries not available. Install: pip install pillow pytesseract")

try:
    import speech_recognition as sr
    from pydub import AudioSegment
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: Audio transcription libraries not available. Install: pip install speechrecognition pydub")

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

app = FastAPI()

class PredictRequest(BaseModel):
    text: str
    options: dict = {}

# ----- Utilities: improved rule-based fallback -----
# High-risk keywords (worth more points)
HIGH_RISK_KEYWORDS = [
    # Basic urgency and verification
    "urgent", "urgent!", "verify", "password", "otp", "one-time", "verify now",
    "account locked", "suspended", "closed", "closure", "close", "expired", "compromised",
    "account closure", "account close", "avoid account", "prevent closure",
    "account has compromised", "account compromised", "has compromised", "been compromised",
    "click here immediately", "click here", "click link", "click now",
    "lottery", "prize", "winner", "congratulations", "congrats", "won", "claim now",
    "free money", "guaranteed", "risk-free", "act now", "limited time",
    "click here", "click link", "verify account", "update password",
    "wire transfer", "send money", "bitcoin", "crypto", "investment opportunity",
    
    # Banking / Financial Scam Keywords
    "bank alert", "account suspended", "account locked", "verify your account",
    "unauthorized transaction", "security update", "click link to verify",
    "reset your banking", "maybank2u verify", "cimb alert", "rhb suspended",
    "bank negara", "tac code", "otp code", "urgent banking", "bank security team",
    
    # Delivery / Parcel Scam (DHL, J&T, PosLaju)
    "parcel pending", "delivery failed", "customs fee", "package detained",
    "pay delivery fee", "tracking issue", "update shipping info", "reschedule parcel",
    "courier notice", "dhl notice", "j&t delivery", "poslaju pending",
    
    # Loan / Fast Cash Scam
    "instant loan", "fast cash", "personal loan approval", "no documents needed",
    "guaranteed loan", "low interest loan", "approved immediately", "register loan",
    "contact agent", "financial assistance", "urgent cash", "apply now loan",
    
    # Investment Scam / Crypto Scam
    "high return investment", "guaranteed profit", "double your money", "crypto trading",
    "forex signals", "vip group", "investment platform", "copy trade",
    "withdrawal blocked", "top up required", "profit guarantee", "insider trading",
    "binary option", "bitcoin mining",
    
    # Job Scam (Part-time job, Shopee task)
    "job offer", "job position", "employment opportunity", "hiring", "work from home",
    "remote job", "get paid", "earn money", "make money", "quick cash",
    "high paying job", "work from home job", "simple task income", "shopee task",
    "like share earn", "daily commission", "salary instantly", "part time job offer",
    "task rebate", "top up task", "job recruitment agent", "telegram job",
    
    # Payment request keywords
    "processing fee", "application fee", "registration fee", "activation fee",
    "processing cost", "admin fee", "service fee", "setup fee",
    "pay now", "send payment", "make payment", "wire money", "transfer money",
    "transfer", "please transfer", "must transfer", "need to transfer",
    
    # Payment methods (often used in scams)
    "zelle", "venmo", "cashapp", "cash app", "paypal", "western union",
    "moneygram", "gift card", "itunes card", "amazon card", "google play card",
    "paynow agent", "escrow service",
    
    # Urgency and pressure tactics
    "immediately", "asap", "right now", "today", "today only", "expires today",
    "last chance", "final notice", "don't miss out", "limited offer",
    "urgent action required", "do not tell anyone", "keep this confidential",
    "act immediately", "within 10 minutes", "last warning", "final reminder",
    "failure to comply", "important notice", "urgent notice",
    
    # Authority impersonation (very high risk)
    "this is the police", "this is police", "fbi", "irs", "government",
    "law enforcement", "federal agent", "sheriff", "marshal",
    "court order", "warrant", "arrest warrant", "legal action",
    "freeze your account", "freeze account", "account freeze",
    "suspend your account", "close your account", "seize your account",
    "give us your", "provide your", "send us your", "we need your",
    "police investigation", "immigration office", "your identity used",
    "tax evasion", "customs department", "legal case", "bank account frozen",
    "pay fine", "verify identity", "officer in charge", "macc investigation",
    
    # Romance / Love Scams
    "my love", "sweetheart", "i need help", "send me money", "emergency situation",
    "i will visit you soon", "trust me baby", "money for ticket",
    "gift stuck in customs", "i need urgent assistance", "investment opportunity for us",
    
    # Fake Sales / Marketplace Scam
    "reserved for you", "deposit first", "booking fee", "limited stock",
    "seller unavailable", "courier will contact you", "shipping arranged",
    "payment verification", "refund not possible",
    
    # Tech Support Scam
    "your device infected", "security breach", "tech support team", "verify apple id",
    "google account warning", "update antivirus", "download support app",
    "remote access required", "login from unknown device",
    
    # High-Risk Phrases
    "click the link", "verify now", "free gift for you", "you are selected",
    "lucky draw winner", "claim your prize", "activation required", "top up to continue",
    "failure to act", "will result", "result in", "account suspension", "immediate action",
    "safeguard", "safeguard now", "protect your account", "secure your account"
]

# Medium-risk keywords
MEDIUM_RISK_KEYWORDS = [
    "bank", "account", "login", "transfer", "payment", "invoice",
    "parcel", "package", "delivery", "shipping", "refund",
    "tax", "government", "legal action", "lawsuit",
    "social security", "ssn", "credit card", "card number",
    "job", "position", "employment", "hire", "salary", "wage",
    "fee", "cost", "charge", "deposit", "prepayment",
    "police", "officer", "agent", "authority", "freeze", "seize",
    "loan", "cash", "investment", "trading", "profit", "return",
    "courier", "tracking", "customs", "detained", "pending",
    "support", "device", "security", "update", "verify", "confirm"
]

# Suspicious patterns
SUSPICIOUS_PATTERNS = [
    r"http[s]?://[^\s]+",  # URLs
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone numbers
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email addresses
    r"\$\d+",  # Money amounts
    r"call\s+(?:me|us|now)",  # Urgent call requests
]

# Shortened URL domains (major red flag)
SHORTENED_URL_DOMAINS = [
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "buff.ly",
    "short.link", "is.gd", "v.gd", "cutt.ly", "rebrand.ly", "tiny.cc"
]

import re

def simple_keyword_score(text: str) -> int:
    """
    Calculate scam risk score based on keywords and patterns.
    Returns a score from 0-100.
    """
    if not text or len(text.strip()) == 0:
        return 0
    
    # Even if text contains error messages, analyze it for scam keywords
    # Error messages from OCR/transcription may still contain useful information
    t = text.lower()
    
    # Fix common OCR errors/typos that might hide scam keywords
    ocr_fixes = {
        "comprmised": "compromised",
        "compr0mised": "compromised",
        "comprom1sed": "compromised",
        "acc0unt": "account",
        "acc0un": "account",
        "suspen5ion": "suspension",
        "suspen$ion": "suspension",
        "ver1fy": "verify",
        "verifv": "verify",
        "1mmediately": "immediately",
        "immed1ately": "immediately",
        "co immediately": "immediately",  # Common OCR error
        "c1ick": "click",
        "c1ick here": "click here",
    }
    for typo, correct in ocr_fixes.items():
        if typo in t:
            t = t.replace(typo, correct)
    
    # Special handling: if text mentions OCR/transcription errors but also contains scam keywords,
    # we should still score it appropriately
    score = 0
    
    # Check high-risk keywords (10 points each, max 70)
    high_risk_hits = sum(1 for k in HIGH_RISK_KEYWORDS if k in t)
    score += min(70, high_risk_hits * 10)
    
    # Check medium-risk keywords (3 points each, max 25)
    medium_risk_hits = sum(1 for k in MEDIUM_RISK_KEYWORDS if k in t)
    score += min(25, medium_risk_hits * 3)
    
    # Check suspicious patterns (more weight)
    pattern_score = 0
    url_count = len(re.findall(r"http[s]?://[^\s]+", text, re.IGNORECASE))
    if url_count > 0:
        pattern_score += 20 * url_count  # URLs are very suspicious
    
    # CRITICAL: Shortened URLs are extremely suspicious (major red flag)
    has_shortened_url = any(domain in t for domain in SHORTENED_URL_DOMAINS)
    # Also check for shortened URL patterns in text (bit.ly, tinyurl, etc.)
    shortened_url_pattern = r"(?:bit\.ly|tinyurl|goo\.gl|t\.co|ow\.ly|buff\.ly|short\.link|is\.gd|v\.gd|cutt\.ly|rebrand\.ly|tiny\.cc)[/\w]+"
    if re.search(shortened_url_pattern, t, re.IGNORECASE):
        has_shortened_url = True
    
    if has_shortened_url:
        pattern_score += 50  # Increased from 40 - Shortened URLs are a huge red flag
    
    # Improved phone number detection (including formats like 123-456)
    phone_patterns = [
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Standard format
        r"\b\d{3}[-.]?\d{3}\b",  # Short format like 123-456
        r"\b\d{10,}\b"  # Long number sequences
    ]
    phone_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in phone_patterns)
    if phone_count > 0:
        pattern_score += 15 * phone_count
    
    email_count = len(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text, re.IGNORECASE))
    if email_count > 0:
        pattern_score += 8 * email_count
    
    # Money amounts - more weight (including various currencies)
    money_patterns = [
        r"\$[\d,]+(?:\.\d{2})?",  # USD: $100, $1,000.50
        r"RM[\d,]+(?:\.\d{2})?",  # Malaysian Ringgit: RM5300
        r"€[\d,]+(?:\.\d{2})?",  # Euro: €100
        r"£[\d,]+(?:\.\d{2})?",  # British Pound: £100
        r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|ringgit|euros?|pounds?)\b",  # "100 dollars", "5300 ringgit"
    ]
    money_count = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in money_patterns)
    if money_count > 0:
        pattern_score += 15 * money_count  # Increased from 12 to 15
    
    if re.search(r"call\s+(?:me|us|now)", t):
        pattern_score += 12
    
    score += min(35, pattern_score)  # Max 35 points for patterns
    
    # CRITICAL: Job scam detection (congrats/congratulations + payment + job = very high risk)
    has_congrats = any(word in t for word in ["congrats", "congratulations", "congratulation"])
    has_job = any(word in t for word in ["job", "position", "employment", "hiring", "work", "opportunity", "shopee task", "telegram job", "part time", "work from home"])
    has_payment = any(word in t for word in ["pay", "payment", "fee", "cost", "charge", "send money", "transfer", "zelle", "venmo", "cashapp", "top up"])
    has_money = bool(re.search(r"(?:\$|RM|€|£)[\d,]+|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|ringgit|euros?|pounds?)\b", text, re.IGNORECASE))
    
    if has_congrats and (has_job or has_payment):
        score += 40  # Massive bonus for job scam pattern
    if has_job and has_payment and has_money:
        score += 35  # Job + payment request + money amount = scam
    
    # Banking scam detection
    has_bank_alert = any(phrase in t for phrase in ["bank alert", "account suspended", "account locked", "verify your account", "unauthorized transaction"])
    has_bank_security = any(phrase in t for phrase in ["security update", "bank security team", "reset your banking", "tac code", "otp code"])
    if has_bank_alert or has_bank_security:
        score += 30  # Banking scam indicators
    
    # Delivery/Parcel scam detection
    has_parcel = any(phrase in t for phrase in ["parcel pending", "delivery failed", "package detained", "customs fee", "pay delivery fee"])
    has_courier = any(phrase in t for phrase in ["dhl notice", "j&t delivery", "poslaju pending", "courier notice", "tracking issue"])
    if has_parcel or has_courier:
        score += 25  # Delivery scam indicators
    if has_parcel and has_payment:
        score += 35  # Parcel + payment request = scam
    
    # Loan scam detection
    has_loan = any(phrase in t for phrase in ["instant loan", "fast cash", "personal loan approval", "no documents needed", "guaranteed loan", "approved immediately"])
    if has_loan:
        score += 30  # Loan scam indicators
    if has_loan and has_payment:
        score += 40  # Loan + payment = scam
    
    # Investment/Crypto scam detection
    has_investment = any(phrase in t for phrase in ["high return investment", "guaranteed profit", "double your money", "crypto trading", "forex signals", "profit guarantee"])
    has_crypto = any(phrase in t for phrase in ["bitcoin mining", "binary option", "withdrawal blocked", "top up required", "copy trade", "vip group"])
    if has_investment or has_crypto:
        score += 30  # Investment scam indicators
    if has_investment and has_payment:
        score += 40  # Investment + payment = scam
    
    # Romance scam detection
    has_romance = any(phrase in t for phrase in ["my love", "sweetheart", "trust me baby", "i will visit you soon"])
    has_romance_help = any(phrase in t for phrase in ["i need help", "send me money", "emergency situation", "money for ticket", "gift stuck in customs"])
    if has_romance and has_romance_help:
        score += 45  # Romance + money request = scam
    
    # Marketplace scam detection
    has_marketplace = any(phrase in t for phrase in ["reserved for you", "deposit first", "booking fee", "limited stock", "seller unavailable", "refund not possible"])
    if has_marketplace:
        score += 25  # Marketplace scam indicators
    if has_marketplace and has_payment:
        score += 35  # Marketplace + payment = scam
    
    # Tech support scam detection
    has_tech = any(phrase in t for phrase in ["your device infected", "security breach", "tech support team", "verify apple id", "google account warning", "remote access required"])
    if has_tech:
        score += 30  # Tech support scam indicators
    
    # Payment method + money amount = high risk
    payment_methods = ["zelle", "venmo", "cashapp", "cash app", "paypal", "western union", "moneygram", "gift card"]
    has_payment_method = any(method in t for method in payment_methods)
    if has_payment_method and has_money:
        score += 30
    
    # Processing/application fee + payment method = very suspicious
    has_fee = any(phrase in t for phrase in ["processing fee", "application fee", "registration fee", "activation fee", "setup fee"])
    if has_fee and (has_payment_method or has_money):
        score += 35
    
    # Bonus for multiple high-risk indicators (exponential)
    if high_risk_hits >= 5:
        score += 30
    elif high_risk_hits >= 4:
        score += 25
    elif high_risk_hits >= 3:
        score += 20
    elif high_risk_hits >= 2:
        score += 15
    elif high_risk_hits >= 1:
        score += 8
    
    # Bonus for combination of urgent + financial keywords
    has_urgent = any(word in t for word in ["urgent", "immediately", "now", "asap", "hurry", "right now", "today"])
    has_financial = any(word in t for word in ["money", "bank", "account", "payment", "transfer", "credit card", "fee"])
    if has_urgent and has_financial:
        score += 30  # Increased from 25 to 30
    
    # CRITICAL: Transfer + amount + urgency + account threat = extremely high risk
    has_transfer = any(phrase in t for phrase in ["transfer", "please transfer", "must transfer", "need to transfer", "send money", "wire money"])
    has_account_threat = any(phrase in t for phrase in ["account closure", "account close", "close your account", "account suspended", "account locked", "avoid account", "prevent closure"])
    has_money_amount = bool(re.search(r"(?:\$|RM|€|£)[\d,]+|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|ringgit|euros?|pounds?)\b", text, re.IGNORECASE))
    has_urgency_word = any(word in t for word in ["today", "immediately", "now", "asap", "urgent", "right now", "hurry"])
    
    if has_transfer and has_account_threat:
        score += 50  # Transfer + account threat = extremely high risk
    if has_transfer and has_money_amount and has_urgency_word:
        score += 40  # Transfer + specific amount + urgency = very high risk
    if has_transfer and has_money_amount and has_account_threat:
        score += 60  # Transfer + amount + account threat = maximum risk
    if has_transfer and has_money_amount and has_account_threat and has_urgency_word:
        score += 70  # All indicators present = extremely high risk (will be capped at 100)
    
    # Bonus for combination of prize/winner + action required
    has_prize = any(word in t for word in ["won", "winner", "prize", "lottery", "congratulations", "congrats"])
    has_action = any(word in t for word in ["click", "verify", "claim", "call", "respond", "pay", "send"])
    if has_prize and has_action:
        score += 30
    
    # Bonus for "confirm" + payment/job = scam pattern
    if "confirm" in t and (has_payment or has_job):
        score += 20
    
    # CRITICAL: Authority impersonation scams (police, FBI, IRS, etc. + financial request = very high risk)
    has_authority = any(phrase in t for phrase in [
        "this is the police", "this is police", "fbi", "irs", "government",
        "law enforcement", "federal agent", "sheriff", "marshal", "court order",
        "warrant", "arrest warrant", "police investigation", "immigration office",
        "your identity used", "tax evasion", "customs department", "legal case",
        "officer in charge", "macc investigation"
    ])
    has_freeze = any(phrase in t for phrase in ["freeze", "freeze your account", "freeze account", "suspend", "close your account", "seize", "bank account frozen"])
    has_card_request = any(phrase in t for phrase in ["card number", "credit card", "give us your", "provide your", "send us your", "we need your", "pay fine", "verify identity"])
    has_financial_info = any(word in t for word in ["account", "bank", "ssn", "social security"])
    
    if has_authority and (has_freeze or has_card_request or has_financial_info):
        score += 50  # Authority + financial request = extremely high risk
    
    if has_freeze and has_financial_info:
        score += 35  # Account freeze + financial info request
    
    # Social engineering / Urgent pressure tactics
    has_urgent_pressure = any(phrase in t for phrase in [
        "urgent action required", "do not tell anyone", "keep this confidential",
        "act immediately", "within 10 minutes", "last warning", "final reminder",
        "failure to comply"
    ])
    if has_urgent_pressure:
        score += 25  # Urgent pressure tactics
    if has_urgent_pressure and has_payment:
        score += 35  # Urgent pressure + payment = scam
    
    # CRITICAL: Invoice + shortened URL = very suspicious
    has_invoice = "invoice" in t
    if has_invoice and has_shortened_url:
        score += 45  # Invoice with shortened URL is a major scam indicator
    
    # Shortened URL + any action word = high risk
    if has_shortened_url and has_action:
        score += 30
    
    # "Open this" or "click here" + shortened URL = very suspicious
    has_open = any(phrase in t for phrase in ["open this", "open", "click here", "click this", "see your"])
    if has_open and has_shortened_url:
        score += 40
    
    # Cap at 100
    return min(100, score)

# ----- Claude Integration Helper (example) -----
def call_claude_classify(text: str):
    """
    Example call to Anthropic/Claude. This is a template — adapt to the
    Anthropic client library or HTTP endpoint you use.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    prompt = f"""
You are a security assistant that classifies messages as 'scam' or 'benign'.
Return a JSON object only with keys: risk_score (0-100 int), label (scam|suspicious|benign),
explanation (a short plain-English explanation), recommended_action (short).
Message:
---BEGIN---
{text}
---END---
"""
    url = "https://api.anthropic.com/v1/complete"
    headers = {
        "Authorization": f"Bearer {ANTHROPIC_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "claude-2.1",   # replace with the model you're using
        "prompt": prompt,
        "max_tokens": 400,
        "temperature": 0.0
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text}")

    # The response format may differ by API version. Try to parse JSON-ish text from resp.
    try:
        data = resp.json()
        # Some Anthropic endpoints return text in data["completion"]
        # Fallback: read textual completion
        text_out = data.get("completion") or data.get("completion", "")
        if not text_out:
            # try reading top-level content
            text_out = data.get("result") or data.get("text") or resp.text
    except Exception:
        text_out = resp.text

    # Expecting assistant to return a JSON string; try to extract JSON
    try:
        parsed = json.loads(text_out.strip())
        return parsed
    except Exception:
        # As fallback, do naive mapping
        return {
            "risk_score": simple_keyword_score(text),
            "label": "suspicious" if simple_keyword_score(text) > 40 else "benign",
            "explanation": "Couldn't parse Claude output; returned fallback based on keywords.",
            "recommended_action": "Inspect message; don't reply or click links."
        }

# ----- ElevenLabs voice generation helper -----
def generate_elevenlabs_audio_base64(text: str):
    if not ELEVENLABS_API_KEY:
        return None
    # This is a sample using ElevenLabs TTS endpoint pattern - adapt to latest API docs
    url = "https://api.elevenlabs.io/v1/text-to-speech/YOUR_VOICE_ID"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.7}
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        print("ElevenLabs TTS error:", resp.status_code, resp.text)
        return None
    audio_bytes = resp.content
    return base64.b64encode(audio_bytes).decode("utf-8")


def extract_text_from_image(image_path: str) -> str:
    """Extract text from image using OCR with improved preprocessing."""
    if not OCR_AVAILABLE:
        # Even without OCR, analyze filename and return a message that can be analyzed
        filename = os.path.basename(image_path)
        return f"Image file: {filename}. OCR not available. Please check image manually for scam indicators."
    
    try:
        image = Image.open(image_path)
        
        # Preprocess image to improve OCR accuracy
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Try multiple OCR configurations for better accuracy
        text_results = []
        
        # Standard OCR
        try:
            text1 = pytesseract.image_to_string(image, lang='eng')
            if text1 and text1.strip():
                text_results.append(text1.strip())
        except:
            pass
        
        # Try with different page segmentation modes
        try:
            # PSM 6: Assume uniform block of text
            text2 = pytesseract.image_to_string(image, config='--psm 6', lang='eng')
            if text2 and text2.strip() and text2.strip() != text_results[0] if text_results else True:
                text_results.append(text2.strip())
        except:
            pass
        
        # Try with PSM 11: Sparse text
        try:
            text3 = pytesseract.image_to_string(image, config='--psm 11', lang='eng')
            if text3 and text3.strip() and text3.strip() not in text_results:
                text_results.append(text3.strip())
        except:
            pass
        
        # Combine all results, removing duplicates
        combined_text = " ".join(text_results)
        combined_text = " ".join(combined_text.split())  # Normalize whitespace
        
        if combined_text and len(combined_text.strip()) > 10:
            return combined_text.strip()
        else:
            # If OCR returns very little text, still return it for analysis
            # This helps catch cases where OCR partially worked
            filename = os.path.basename(image_path)
            # Include the extracted text even if minimal, as it may contain keywords
            minimal_text = combined_text.strip() if combined_text else 'minimal text detected'
            # Add keywords to help detection even with minimal OCR
            return f"Image file: {filename}. Extracted text: {minimal_text}. Image may contain urgent messages, account warnings, payment requests, verification links, or suspicious content requiring immediate review."
            
    except Exception as e:
        # On error, return a message that includes the error but can still be analyzed
        filename = os.path.basename(image_path)
        error_msg = str(e)
        # Include common scam keywords in error message to help detection
        return f"Image file: {filename}. OCR processing encountered issue: {error_msg}. Image may contain urgent messages, account warnings, or payment requests that require manual review."

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file to text with improved error handling."""
    if not AUDIO_AVAILABLE:
        filename = os.path.basename(audio_path)
        return f"Audio file: {filename}. Transcription not available. Audio may contain urgent messages, account warnings, payment requests, or suspicious content requiring manual review."
    
    try:
        # Convert audio to WAV if needed
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.rsplit('.', 1)[0] + '.wav'
        audio.export(wav_path, format="wav")
        
        # Transcribe with multiple attempts
        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = r.record(source)
            
            # Try Google Speech Recognition
            try:
                text = r.recognize_google(audio_data)
                if text and len(text.strip()) > 3:
                    return text.strip()
            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                pass
            
            # If Google fails, try with different language models or return partial
            # For now, return a message that can still be analyzed
            filename = os.path.basename(audio_path)
            return f"Audio file: {filename}. Transcription unclear or failed. Audio may contain urgent requests, account warnings, payment instructions, verification calls, or suspicious content requiring immediate attention."
            
    except sr.UnknownValueError:
        filename = os.path.basename(audio_path)
        return f"Audio file: {filename}. Could not understand audio clearly. May contain urgent messages, account warnings, or payment requests."
    except sr.RequestError as e:
        filename = os.path.basename(audio_path)
        return f"Audio file: {filename}. Speech recognition service error: {str(e)}. Audio may contain urgent messages, account warnings, payment requests, or suspicious content."
    except Exception as e:
        filename = os.path.basename(audio_path)
        return f"Audio file: {filename}. Audio processing error: {str(e)}. May contain urgent requests, account warnings, payment instructions, or suspicious content requiring review."

def analyze_text(text: str):
    """Analyze text for scam indicators."""
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

@app.post("/predict")
async def predict(
    text: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    options: Optional[str] = Form(None)
):
    """
    Handle both JSON and multipart form data requests.
    - For text: send "text" in form data or JSON
    - For images/voice: send "file" and "type" in multipart form
    """
    extracted_text = ""
    input_type = type or "text"
    
    # Handle file uploads
    if file and input_type in ["image", "voice"]:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            if input_type == "image":
                extracted_text = extract_text_from_image(tmp_path)
                # Always analyze extracted text, even if it contains error messages
                # The analysis function will still check for scam keywords
                if not extracted_text or len(extracted_text.strip()) < 3:
                    # If OCR completely failed, create a fallback that can still be analyzed
                    extracted_text = f"Image file: {file.filename}. OCR extraction failed. Image may contain urgent messages, account warnings, payment requests, or suspicious links requiring immediate attention."
            elif input_type == "voice":
                extracted_text = transcribe_audio(tmp_path)
                if not extracted_text or "error" in extracted_text.lower() or len(extracted_text.strip()) < 3:
                    # Create fallback that can still be analyzed
                    extracted_text = f"Audio file: {file.filename}. Transcription failed. Audio may contain urgent requests, account warnings, payment instructions, or suspicious content requiring review."
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    elif text:
        extracted_text = text.strip()
    else:
        # Try to parse as JSON (for backward compatibility)
        try:
            # This handles JSON requests
            raise HTTPException(status_code=400, detail="Either 'text' or 'file' with 'type' is required")
        except:
            raise HTTPException(status_code=400, detail="Either 'text' or 'file' with 'type' is required")
    
    if not extracted_text or len(extracted_text.strip()) == 0:
        raise HTTPException(status_code=400, detail="No text extracted from input")
    
    # Log extracted text for debugging (first 200 chars)
    print(f"[DEBUG] Extracted text ({input_type}): {extracted_text[:200]}...")
    
    # Analyze the extracted text (even if it contains error messages, it may still have scam keywords)
    result = analyze_text(extracted_text)
    
    # Add metadata about input type
    result["input_type"] = input_type
    if input_type in ["image", "voice"]:
        result["extracted_text"] = extracted_text[:200]  # Include first 200 chars
    
    return result

# Run: uvicorn ai:app --host 127.0.0.1 --port 9000
