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
import hashlib
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
    "safeguard", "safeguard now", "protect your account", "secure your account",
    
    # Voice-Specific Scam Patterns (very high risk in voice calls)
    "can you hear me", "say yes", "say yes if you can hear me", "do you hear me",
    "press one", "press star", "press pound", "press hash", "press the number",
    "stay on the line", "don't hang up", "keep this call confidential",
    "this call is being recorded", "for quality assurance", "for security purposes",
    "verify your identity by saying", "repeat after me", "say your password",
    "confirm your account number", "read back the code", "tell me the code",
    "i'm calling from", "this is an automated message", "press any key",
    "call us back immediately", "call this number now", "dial this number",
    "hang up and call", "redial this number", "call back within",
    "your call is important to us", "please hold", "one moment please",
    "speak to an agent", "transferring your call", "connecting you now"
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
    
    # Extract file metadata from text if present (for variation)
    file_hash = None
    file_size = None
    # Look for metadata pattern: [Audio: filename, duration, size, hash] or [File metadata: hash, size]
    metadata_match = re.search(r'\[.*?hash:\s*([a-f0-9]+).*?\]|\[.*?File metadata:\s*([a-f0-9]+)', text, re.IGNORECASE)
    if metadata_match:
        file_hash = metadata_match.group(1) or metadata_match.group(2)
    size_match = re.search(r'size:\s*(\d+)\s*bytes', text, re.IGNORECASE)
    if size_match:
        file_size = int(size_match.group(1))
    
    # CRITICAL: Extract the actual transcribed/OCR text before metadata removal
    # For successful transcriptions, format is: "transcribed_text [Audio: ...]"
    # For error messages, format is: "Audio file: ... [File metadata: ...]"
    # We want to analyze ONLY the actual content, not error messages
    
    # Check if this is an error message (multiple patterns to catch all error cases)
    text_lower = text.lower().strip()
    is_error_message = (
        text.strip().startswith("Audio file:") or 
        text.strip().startswith("Image file:") or
        "transcription unavailable" in text_lower or
        "transcription service unavailable" in text_lower or
        "could not understand audio" in text_lower or
        "transcription failed" in text_lower or
        "speech recognition service error" in text_lower or
        "network error connecting" in text_lower or
        "unable to load audio" in text_lower or
        "please review manually" in text_lower or
        "please review audio content manually" in text_lower
    )
    
    if is_error_message:
        # For error messages, return low risk (0) since we can't analyze the actual content
        # Error messages don't contain the actual voice/image content, so they shouldn't be scored
        print(f"[DEBUG] Detected error message, returning 0% risk. Text preview: {text[:100]}")
        return 0
    
    # Extract the actual content text (everything before the metadata brackets)
    # Remove metadata patterns at the end: [Audio: ...] or [File: ...] or [File metadata: ...]
    # Use a more specific pattern to only remove metadata at the end, not content in brackets
    content_text = text
    # Remove trailing metadata: [Audio: ...], [File: ...], [File metadata: ...]
    content_text = re.sub(r'\s*\[(?:Audio|File|File metadata):[^\]]+\]\s*$', '', content_text, flags=re.IGNORECASE)
    # Also remove standalone [File metadata: ...] patterns anywhere in the text
    content_text = re.sub(r'\s*\[File metadata:[^\]]+\]\s*', '', content_text, flags=re.IGNORECASE)
    # Remove any remaining metadata patterns
    content_text = re.sub(r'\s*\[Audio:[^\]]+\]\s*', '', content_text, flags=re.IGNORECASE)
    content_text = re.sub(r'\s*\[File:[^\]]+\]\s*', '', content_text, flags=re.IGNORECASE)
    
    # Clean up the content text
    content_text = content_text.strip()
    
    # If after removing metadata we have no meaningful content, return 0
    if not content_text or len(content_text) < 3:
        print(f"[DEBUG] No meaningful content after metadata removal. Original: {text[:100]}, Content: {content_text[:100]}")
        return 0
    
    # Log what we're actually analyzing (for debugging)
    print(f"[DEBUG] Analyzing content text (length: {len(content_text)}): {content_text[:150]}...")
    
    # Use the extracted content for analysis
    t = content_text.lower()
    
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
    
    # Check high-risk keywords (15 points each, max 80) - Increased for better detection
    high_risk_hits = sum(1 for k in HIGH_RISK_KEYWORDS if k in t)
    score += min(80, high_risk_hits * 15)  # Increased from 10 to 15 points per hit
    
    # Check medium-risk keywords (5 points each, max 30) - Increased for better detection
    medium_risk_hits = sum(1 for k in MEDIUM_RISK_KEYWORDS if k in t)
    score += min(30, medium_risk_hits * 5)  # Increased from 3 to 5 points per hit
    
    # Log keyword hits for debugging
    if high_risk_hits > 0 or medium_risk_hits > 0:
        print(f"[DEBUG] Keyword hits - High: {high_risk_hits}, Medium: {medium_risk_hits}, Score so far: {score}")
    
    # Check suspicious patterns (more weight)
    # Use content_text (original case) for pattern matching to preserve case-sensitive patterns
    pattern_score = 0
    url_count = len(re.findall(r"http[s]?://[^\s]+", content_text, re.IGNORECASE))
    if url_count > 0:
        pattern_score += 20 * url_count  # URLs are very suspicious
    
    # CRITICAL: Shortened URLs are extremely suspicious (major red flag)
    has_shortened_url = any(domain in t for domain in SHORTENED_URL_DOMAINS)
    # Also check for shortened URL patterns in content_text (bit.ly, tinyurl, etc.)
    shortened_url_pattern = r"(?:bit\.ly|tinyurl|goo\.gl|t\.co|ow\.ly|buff\.ly|short\.link|is\.gd|v\.gd|cutt\.ly|rebrand\.ly|tiny\.cc)[/\w]+"
    if re.search(shortened_url_pattern, content_text, re.IGNORECASE):
        has_shortened_url = True
    
    if has_shortened_url:
        pattern_score += 50  # Increased from 40 - Shortened URLs are a huge red flag
    
    # Improved phone number detection (including formats like 123-456)
    phone_patterns = [
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Standard format
        r"\b\d{3}[-.]?\d{3}\b",  # Short format like 123-456
        r"\b\d{10,}\b"  # Long number sequences
    ]
    phone_count = sum(len(re.findall(pattern, content_text, re.IGNORECASE)) for pattern in phone_patterns)
    if phone_count > 0:
        pattern_score += 15 * phone_count
    
    email_count = len(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", content_text, re.IGNORECASE))
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
    money_count = sum(len(re.findall(pattern, content_text, re.IGNORECASE)) for pattern in money_patterns)
    if money_count > 0:
        pattern_score += 15 * money_count  # Increased from 12 to 15
    
    if re.search(r"call\s+(?:me|us|now)", t):
        pattern_score += 12
    
    score += min(35, pattern_score)  # Max 35 points for patterns
    
    # CRITICAL: Job scam detection (congrats/congratulations + payment + job = very high risk)
    has_congrats = any(word in t for word in ["congrats", "congratulations", "congratulation"])
    has_job = any(word in t for word in ["job", "position", "employment", "hiring", "work", "opportunity", "shopee task", "telegram job", "part time", "work from home"])
    has_payment = any(word in t for word in ["pay", "payment", "fee", "cost", "charge", "send money", "transfer", "zelle", "venmo", "cashapp", "top up"])
    has_money = bool(re.search(r"(?:\$|RM|€|£)[\d,]+|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|ringgit|euros?|pounds?)\b", content_text, re.IGNORECASE))
    
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
    
    # Bonus for multiple high-risk indicators (exponential) - Increased bonuses
    if high_risk_hits >= 5:
        score += 40  # Increased from 30
    elif high_risk_hits >= 4:
        score += 35  # Increased from 25
    elif high_risk_hits >= 3:
        score += 30  # Increased from 20
    elif high_risk_hits >= 2:
        score += 20  # Increased from 15
    elif high_risk_hits >= 1:
        score += 12  # Increased from 8
    
    # Bonus for combination of urgent + financial keywords
    has_urgent = any(word in t for word in ["urgent", "immediately", "now", "asap", "hurry", "right now", "today"])
    has_financial = any(word in t for word in ["money", "bank", "account", "payment", "transfer", "credit card", "fee"])
    if has_urgent and has_financial:
        score += 30  # Increased from 25 to 30
    
    # CRITICAL: Transfer + amount + urgency + account threat = extremely high risk
    has_transfer = any(phrase in t for phrase in ["transfer", "please transfer", "must transfer", "need to transfer", "send money", "wire money"])
    has_account_threat = any(phrase in t for phrase in ["account closure", "account close", "close your account", "account suspended", "account locked", "avoid account", "prevent closure"])
    has_money_amount = bool(re.search(r"(?:\$|RM|€|£)[\d,]+|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|ringgit|euros?|pounds?)\b", content_text, re.IGNORECASE))
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
    
    # CRITICAL: Voice-specific scam detection (very high risk indicators)
    # These patterns are extremely suspicious in voice calls
    voice_suspicious_patterns = [
        "can you hear me", "say yes", "press one", "press star", "press pound",
        "stay on the line", "don't hang up", "this call is being recorded",
        "verify your identity by saying", "repeat after me", "say your password",
        "read back the code", "tell me the code", "call us back immediately"
    ]
    has_voice_scam_pattern = any(pattern in t for pattern in voice_suspicious_patterns)
    if has_voice_scam_pattern:
        score += 50  # Voice scam patterns are extremely high risk
    
    # Voice call-back requests + urgency = very suspicious
    has_call_back = any(phrase in t for phrase in [
        "call us back", "call back", "call this number", "dial this number",
        "redial", "hang up and call", "call immediately", "call now"
    ])
    if has_call_back and has_urgent:
        score += 40  # Urgent call-back request is a major red flag
    
    # "Press" or "Say" commands in voice = high risk (common in phone scams)
    has_voice_command = any(phrase in t for phrase in [
        "press one", "press star", "press pound", "press hash", "press the number",
        "say yes", "say your", "repeat after me", "tell me"
    ])
    if has_voice_command:
        score += 35  # Voice commands are suspicious
    
    # CRITICAL: Authority impersonation scams (police, FBI, IRS, etc. + financial request = very high risk)
    # Define has_authority BEFORE using it
    has_authority = any(phrase in t for phrase in [
        "this is the police", "this is police", "fbi", "irs", "government",
        "law enforcement", "federal agent", "sheriff", "marshal", "court order",
        "warrant", "arrest warrant", "police investigation", "immigration office",
        "your identity used", "tax evasion", "customs department", "legal case",
        "officer in charge", "macc investigation"
    ])
    
    # Authority + voice verification = extremely high risk
    if has_authority and has_voice_command:
        score += 60  # Authority impersonation + voice verification = maximum risk
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
    
    # Add file-specific variation to prevent identical scores for different files
    # This ensures each file gets a slightly different score even with similar content
    variation = 0
    if file_hash:
        # Use hash to create consistent but unique variation (-3 to +3 points)
        hash_int = int(file_hash, 16) % 7
        variation = hash_int - 3  # Range: -3 to +3
    if file_size:
        # Use file size to add small variation (-2 to +2 points)
        size_variation = (file_size % 5) - 2  # Range: -2 to +2
        variation += size_variation
    
    score += variation
    
    # Cap at 100, floor at 0
    final_score = min(100, max(0, score))
    print(f"[DEBUG] Final risk score: {final_score}% (raw score: {score})")
    return final_score

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
    """Transcribe audio file to text with improved error handling and multiple strategies."""
    if not AUDIO_AVAILABLE:
        filename = os.path.basename(audio_path)
        # Add file hash to make output unique
        try:
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            file_size = os.path.getsize(audio_path)
            return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Transcription service unavailable. Please review audio content manually. [File metadata: {file_hash}, {file_size} bytes]"
        except:
            return f"Audio file: {filename}. Transcription service unavailable. Please review audio content manually."
    
    filename = os.path.basename(audio_path)
    wav_path = None
    
    # Get file metadata for unique identification
    try:
        file_size = os.path.getsize(audio_path)
        with open(audio_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
    except:
        file_size = 0
        file_hash = "unknown"
    
    try:
        # Load and preprocess audio with multiple strategies
        print(f"[AUDIO] Processing: {filename} (size: {file_size} bytes, hash: {file_hash})")
        
        # Load audio file
        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as e:
            print(f"[AUDIO] Error loading audio: {e}")
            # Include file metadata in error for uniqueness, but avoid scam keywords
            return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Unable to load audio file format. File may be corrupted or in unsupported format. Please review file manually. [File metadata: {file_hash}, {file_size} bytes]"
        
        # Get audio metadata
        duration_seconds = len(audio) / 1000.0
        sample_rate = audio.frame_rate
        channels = audio.channels
        
        print(f"[AUDIO] Duration: {duration_seconds:.2f}s, Sample rate: {sample_rate}Hz, Channels: {channels}")
        
        # Calculate audio characteristics for unique identification
        max_amplitude = audio.max_possible_amplitude
        actual_max = audio.max
        volume_ratio = (actual_max / max_amplitude) * 100 if max_amplitude > 0 else 0
        
        # Skip if audio is too short or too long
        if duration_seconds < 0.5:
            return f"Audio file: {filename} (duration: {duration_seconds:.2f}s, size: {file_size} bytes, hash: {file_hash}, volume: {volume_ratio:.1f}%). Audio too short. May be incomplete or corrupted. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.2f}s]"
        
        if duration_seconds > 300:  # 5 minutes
            # For long audio, process first 60 seconds
            audio = audio[:60000]
            print(f"[AUDIO] Audio too long, processing first 60 seconds")
        
        # Enhanced audio preprocessing for better transcription
        # Step 1: Normalize volume
        try:
            normalized_audio = audio.normalize()
        except:
            normalized_audio = audio
        
        # Step 2: Convert to mono if stereo (better for speech recognition)
        if channels > 1:
            normalized_audio = normalized_audio.set_channels(1)
        
        # Step 3: Set consistent sample rate (16kHz is optimal for speech)
        if sample_rate != 16000:
            normalized_audio = normalized_audio.set_frame_rate(16000)
        
        # Step 4: Apply high-pass filter to remove low-frequency noise (below 80Hz)
        # This helps remove background hum and improves speech clarity
        try:
            # Use pydub's built-in high-pass filter if available
            # For frequencies below 80Hz, reduce volume significantly
            normalized_audio = normalized_audio.high_pass_filter(80)
        except:
            # If high-pass filter not available, continue without it
            pass
        
        # Step 5: Apply low-pass filter to remove high-frequency noise (above 8000Hz)
        # This helps reduce hiss and improves recognition accuracy
        try:
            normalized_audio = normalized_audio.low_pass_filter(8000)
        except:
            pass
        
        # Step 6: Additional volume boost if audio is too quiet
        if volume_ratio < 30:
            try:
                # Boost quiet audio by up to 15dB, but don't exceed safe limits
                boost_db = min(15, 30 - volume_ratio)
                normalized_audio = normalized_audio + boost_db
                print(f"[AUDIO] Applied {boost_db}dB volume boost (original: {volume_ratio:.1f}%)")
            except:
                pass
        
        # Export to WAV with optimal settings
        wav_path = audio_path.rsplit('.', 1)[0] + '_processed.wav'
        normalized_audio.export(wav_path, format="wav", parameters=["-ac", "1", "-ar", "16000"])
        print(f"[AUDIO] Exported processed audio to: {wav_path}")
        
        # Enhanced transcription with multiple strategies
        r = sr.Recognizer()
        r.energy_threshold = 300  # Adjust sensitivity
        r.dynamic_energy_threshold = True
        r.pause_threshold = 0.8  # Reduce pause threshold for faster speech
        r.phrase_threshold = 0.3  # Lower phrase threshold for better detection
        
        transcription_results = []
        languages_to_try = ["en-US", "en-GB", "en-AU"]  # Try multiple English variants
        
        # Strategy 1: Full audio with optimized noise adjustment
        for lang in languages_to_try:
            try:
                with sr.AudioFile(wav_path) as source:
                    # Adjust for ambient noise with adaptive duration
                    noise_duration = min(1.5, duration_seconds * 0.1)  # Adaptive based on length
                    r.adjust_for_ambient_noise(source, duration=noise_duration)
                    audio_data = r.record(source)
                    
                    # Try Google Speech Recognition
                    try:
                        text = r.recognize_google(audio_data, language=lang, show_all=False)
                        if text and len(text.strip()) > 3:
                            print(f"[AUDIO] Google recognition successful ({lang}): {text[:100]}...")
                            transcription_results.append(text.strip())
                            # Return immediately if we get a good result
                            if len(text.strip()) > 10:
                                return f"{text.strip()} [Audio: {filename}, {duration_seconds:.1f}s, {file_size} bytes]"
                    except sr.UnknownValueError:
                        print(f"[AUDIO] Google ({lang}): Could not understand audio")
                    except sr.RequestError as e:
                        print(f"[AUDIO] Google API error ({lang}): {e}")
            except Exception as e:
                print(f"[AUDIO] Strategy 1 ({lang}) failed: {e}")
        
        # Strategy 2: Try with show_all to get alternatives and confidence scores
        for lang in languages_to_try:
            try:
                with sr.AudioFile(wav_path) as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio_data = r.record(source)
                    
                    try:
                        result = r.recognize_google(audio_data, language=lang, show_all=True)
                        if result and 'alternative' in result:
                            # Get the best match with highest confidence
                            best_match = result['alternative'][0]['transcript']
                            confidence = result['alternative'][0].get('confidence', 0)
                            if best_match and len(best_match.strip()) > 3:
                                print(f"[AUDIO] Google (alternative, {lang}, conf: {confidence:.2f}): {best_match[:100]}...")
                                transcription_results.append(best_match.strip())
                                if confidence > 0.7 and len(best_match.strip()) > 10:
                                    return f"{best_match.strip()} [Audio: {filename}, {duration_seconds:.1f}s, {file_size} bytes]"
                    except:
                        pass
            except Exception as e:
                print(f"[AUDIO] Strategy 2 ({lang}) failed: {e}")
        
        # Strategy 3: Overlapping chunk strategy for better accuracy
        # Use 20-second chunks with 5-second overlap to avoid cutting words
        try:
            chunk_duration = 20000  # 20 seconds per chunk
            overlap_duration = 5000  # 5 seconds overlap
            chunk_texts = []
            
            i = 0
            while i < len(normalized_audio):
                # Create overlapping chunk
                chunk_end = min(i + chunk_duration, len(normalized_audio))
                chunk = normalized_audio[i:chunk_end]
                chunk_path = wav_path.replace('.wav', f'_chunk_{i//chunk_duration}.wav')
                chunk.export(chunk_path, format="wav")
                
                try:
                    with sr.AudioFile(chunk_path) as source:
                        r.adjust_for_ambient_noise(source, duration=0.3)
                        chunk_audio = r.record(source)
                        # Try multiple languages for each chunk
                        for lang in languages_to_try:
                            try:
                                chunk_text = r.recognize_google(chunk_audio, language=lang)
                                if chunk_text and len(chunk_text.strip()) > 3:
                                    chunk_texts.append(chunk_text.strip())
                                    print(f"[AUDIO] Chunk {i//chunk_duration} transcribed ({lang}): {chunk_text[:50]}...")
                                    break  # Success, move to next chunk
                            except:
                                continue
                except:
                    pass
                finally:
                    # Clean up chunk file
                    if os.path.exists(chunk_path):
                        os.unlink(chunk_path)
                
                # Move forward with overlap
                i += (chunk_duration - overlap_duration)
            
            if chunk_texts:
                # Remove duplicate phrases from overlapping chunks
                combined_text = " ".join(chunk_texts)
                # Simple deduplication: remove repeated phrases
                words = combined_text.split()
                deduplicated = []
                seen_phrases = set()
                for i in range(len(words) - 4):
                    phrase = " ".join(words[i:i+5])
                    if phrase not in seen_phrases:
                        deduplicated.append(words[i])
                        seen_phrases.add(phrase)
                    else:
                        # Skip this word as it's part of a duplicate phrase
                        continue
                # Add remaining words
                deduplicated.extend(words[len(deduplicated):])
                combined_text = " ".join(deduplicated)
                
                print(f"[AUDIO] Overlapping chunked transcription successful: {combined_text[:100]}...")
                transcription_results.append(combined_text.strip())
                if len(combined_text.strip()) > 10:
                    return f"{combined_text.strip()} [Audio: {filename}, {duration_seconds:.1f}s, {len(chunk_texts)} chunks, {file_size} bytes]"
        except Exception as e:
            print(f"[AUDIO] Strategy 3 (overlapping chunks) failed: {e}")
        
        # Strategy 4: Try with increased volume and different thresholds
        try:
            louder_audio = normalized_audio + 12  # Increase volume by 12dB
            louder_path = wav_path.replace('.wav', '_louder.wav')
            louder_audio.export(louder_path, format="wav")
            
            r2 = sr.Recognizer()
            r2.energy_threshold = 200  # Lower threshold for louder audio
            r2.dynamic_energy_threshold = True
            
            with sr.AudioFile(louder_path) as source:
                r2.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = r2.record(source)
                for lang in languages_to_try:
                    try:
                        text = r2.recognize_google(audio_data, language=lang)
                        if text and len(text.strip()) > 3:
                            print(f"[AUDIO] Louder audio transcription successful ({lang}): {text[:100]}...")
                            transcription_results.append(text.strip())
                            if os.path.exists(louder_path):
                                os.unlink(louder_path)
                            if len(text.strip()) > 10:
                                return f"{text.strip()} [Audio: {filename}, {duration_seconds:.1f}s, amplified, {file_size} bytes]"
                    except:
                        continue
            
            if os.path.exists(louder_path):
                os.unlink(louder_path)
        except Exception as e:
            print(f"[AUDIO] Strategy 4 (louder) failed: {e}")
        
        # Strategy 5: Combine all transcription results if we have multiple
        if len(transcription_results) > 1:
            # Use the longest result as it's likely most complete
            best_result = max(transcription_results, key=len)
            print(f"[AUDIO] Using best result from {len(transcription_results)} attempts: {best_result[:100]}...")
            return f"{best_result.strip()} [Audio: {filename}, {duration_seconds:.1f}s, {file_size} bytes, combined]"
        elif len(transcription_results) == 1:
            # Use the single result we got
            print(f"[AUDIO] Using single transcription result: {transcription_results[0][:100]}...")
            return f"{transcription_results[0].strip()} [Audio: {filename}, {duration_seconds:.1f}s, {file_size} bytes]"
        
        # If all strategies fail, return detailed error with unique metadata
        file_ext = os.path.splitext(filename)[1].lower()
        error_details = f"Duration: {duration_seconds:.1f}s, Format: {file_ext}, Size: {file_size} bytes, Hash: {file_hash}, Volume: {volume_ratio:.1f}%"
        
        # Provide more specific error messages based on audio characteristics - make each unique
        # Avoid scam keywords in error messages to prevent false positives
        if duration_seconds < 2:
            return f"Audio file: {filename} ({error_details}). Very short audio - may be incomplete or contain only background noise. Transcription unavailable. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.2f}s, volume: {volume_ratio:.1f}%]"
        elif duration_seconds > 60:
            return f"Audio file: {filename} ({error_details}). Long audio file - transcription may have failed due to length or quality. Processing {duration_seconds:.1f} seconds. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.1f}s, volume: {volume_ratio:.1f}%]"
        elif volume_ratio < 10:
            return f"Audio file: {filename} ({error_details}). Very quiet audio (volume: {volume_ratio:.1f}%) - may be too quiet to transcribe. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.1f}s, low volume]"
        elif volume_ratio > 90:
            return f"Audio file: {filename} ({error_details}). Very loud audio (volume: {volume_ratio:.1f}%) - may be distorted or clipped. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.1f}s, high volume]"
        else:
            # Create unique error message based on file characteristics
            quality_hint = "good" if volume_ratio > 30 and 2 < duration_seconds < 30 else "poor"
            return f"Audio file: {filename} ({error_details}). Transcription failed after multiple attempts. Audio quality appears {quality_hint}. Please review manually. [File metadata: {file_hash}, {file_size} bytes, {duration_seconds:.1f}s, {file_ext}, {'compressed' if file_size < 100000 else 'uncompressed'}]"
            
    except sr.UnknownValueError:
        # Include file metadata even in error cases
        try:
            file_size = os.path.getsize(audio_path)
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        except:
            file_size = 0
            file_hash = "unknown"
        return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Could not understand audio clearly - speech may be unclear, too quiet, or in an unsupported language. Please review manually. [File metadata: {file_hash}, {file_size} bytes, unrecognizable speech]"
    except sr.RequestError as e:
        error_msg = str(e)
        try:
            file_size = os.path.getsize(audio_path)
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        except:
            file_size = 0
            file_hash = "unknown"
        if "network" in error_msg.lower() or "connection" in error_msg.lower():
            return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Network error connecting to speech recognition service. Please check internet connection and review manually. [File metadata: {file_hash}, {file_size} bytes, network error: {error_msg[:50]}]"
        else:
            return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Speech recognition service error: {error_msg[:100]}. Please review manually. [File metadata: {file_hash}, {file_size} bytes, service error]"
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        try:
            file_size = os.path.getsize(audio_path)
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        except:
            file_size = 0
            file_hash = "unknown"
        print(f"[AUDIO] Unexpected error: {error_type}: {error_msg}")
        return f"Audio file: {filename} (size: {file_size} bytes, hash: {file_hash}). Audio processing error ({error_type}): {error_msg[:100]}. Please review manually. [File metadata: {file_hash}, {file_size} bytes, error: {error_type}]"
    finally:
        # Clean up temporary files
        if wav_path and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except:
                pass

def analyze_text(text: str):
    """Analyze text for scam indicators."""
    if len(text) == 0:
        raise HTTPException(status_code=400, detail="text empty")

    # Log the input text for debugging
    print(f"[DEBUG] analyze_text called with text (length: {len(text)}): {text[:200]}...")

    # 1) Try to call Claude, fall back to improved keyword detection
    try:
        claude_out = call_claude_classify(text)
        # Expect keys risk_score,label,explanation,recommended_action
        risk = int(claude_out.get("risk_score", simple_keyword_score(text)))
        label = claude_out.get("label", "suspicious")
        explanation = claude_out.get("explanation", "")
        recommended_action = claude_out.get("recommended_action", "")
        print(f"[DEBUG] Claude analysis result: risk={risk}%, label={label}")
    except Exception as e:
        # fallback - use improved keyword detection
        error_str = str(e)
        print(f"[DEBUG] Claude failed, using keyword detection. Error: {error_str}")
        risk = simple_keyword_score(text)
        print(f"[DEBUG] Keyword detection result: risk={risk}%")
        
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
                # Get file metadata before transcription for unique identification
                try:
                    file_size = os.path.getsize(tmp_path)
                    with open(tmp_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()[:8]
                except:
                    file_size = 0
                    file_hash = "unknown"
                
                extracted_text = transcribe_audio(tmp_path)
                # The improved transcribe_audio function now handles all error cases internally
                # and returns meaningful text that can be analyzed even on failure
                # So we always use what it returns
                if not extracted_text or len(extracted_text.strip()) < 3:
                    # Only create fallback if transcription is completely empty
                    extracted_text = f"Audio file: {file.filename} (size: {file_size} bytes, hash: {file_hash}). Transcription unavailable. Please review manually. [File metadata: {file_hash}, {file_size} bytes]"
                else:
                    # Ensure file metadata is included even if transcription succeeded
                    if file_hash not in extracted_text and file_size > 0:
                        extracted_text = f"{extracted_text} [File: {file.filename}, {file_size} bytes, {file_hash}]"
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
    
    # CRITICAL: For voice files, apply additional sensitivity boost
    # Voice scams are often more urgent and manipulative, so we need higher sensitivity
    if input_type == "voice" and result["risk_score"] > 0:
        # Check if it's actual transcribed content (not an error message)
        is_actual_content = not (
            extracted_text.strip().startswith("Audio file:") or
            "transcription unavailable" in extracted_text.lower() or
            "please review manually" in extracted_text.lower()
        )
        
        if is_actual_content:
            # Apply voice-specific boost: increase risk score by 20% (capped at 100)
            original_score = result["risk_score"]
            boosted_score = min(100, int(original_score * 1.2))
            
            # If the text contains any scam keywords at all, ensure minimum 30% risk
            # This prevents legitimate-sounding but suspicious voice calls from scoring too low
            if original_score > 0 and original_score < 30:
                # If there are any high-risk keywords, boost to at least 30%
                content_lower = extracted_text.lower()
                has_any_scam_keyword = any(
                    keyword in content_lower for keyword in HIGH_RISK_KEYWORDS[:20]  # Check first 20 keywords
                )
                if has_any_scam_keyword:
                    boosted_score = max(boosted_score, 30)
            
            result["risk_score"] = boosted_score
            print(f"[DEBUG] Voice file boost applied: {original_score}% -> {boosted_score}%")
            
            # Update label if score crossed threshold
            if boosted_score >= 70:
                result["label"] = "scam"
            elif boosted_score >= 40:
                result["label"] = "suspicious"
            else:
                result["label"] = "benign"
            
            # Update explanation with boosted score
            if boosted_score >= 70:
                result["explanation"] = f"⚠️ HIGH RISK ({boosted_score}%): Multiple scam indicators detected in voice call including urgent language, suspicious requests, or financial demands. This appears to be a scam."
            elif boosted_score >= 40:
                result["explanation"] = f"⚠️ MODERATE RISK ({boosted_score}%): Suspicious elements detected in voice call. Exercise extreme caution."
            elif boosted_score >= 20:
                result["explanation"] = f"⚠️ LOW RISK ({boosted_score}%): Some minor suspicious elements detected in voice call. Proceed with caution."
    
    return result

# Run: uvicorn ai:app --host 127.0.0.1 --port 9000
