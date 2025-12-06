"use client";

import { useEffect, useMemo, useState } from "react";
import AuthModal from "../components/AuthModal";

// Helper to get current time string (client-side only)
const getCurrentTimeString = () => {
  if (typeof window === 'undefined') return '';
  return new Date().toLocaleTimeString();
};

type Channel = "voice" | "text" | "image";
type RiskLevel = "pending" | "safe" | "warn" | "danger";

type ScanResult = {
  level: RiskLevel;
  score: number;
  reason: string;
  channel: Channel;
  timestamp: string;
};

const channelCopy: Record<
  Channel,
  { label: string; placeholder: string; hint: string; badge: string }
> = {
  voice: {
    label: "Voice",
    placeholder: "Drop .mp3 or .wav, or paste transcription/summary…",
    hint: "Tone, urgency, impersonation cues, caller ID mismatch.",
    badge: "",
  },
  text: {
    label: "Text",
    placeholder: "Paste the SMS, email, or chat transcript…",
    hint: "Phishing keywords, spoofed links, payment requests.",
    badge: "",
  },
  image: {
    label: "Image",
    placeholder: "Drag in a JPEG/PNG or describe the uploaded ID/invoice…",
    hint: "Drag-and-drop JPEG/PNG; check tampered logos or edits.",
    badge: "",
  },
};


const riskPalette: Record<RiskLevel, string> = {
  pending: "bg-white/5 text-slate-50 border-white/10",
  safe: "bg-emerald-500/15 text-emerald-50 border-emerald-400/50",
  warn: "bg-amber-500/15 text-amber-50 border-amber-400/70",
  danger: "bg-rose-600/15 text-rose-50 border-rose-500/70",
};

const riskAccent: Record<RiskLevel, string> = {
  pending: "text-slate-50",
  safe: "text-emerald-100",
  warn: "text-amber-100",
  danger: "text-rose-100",
};

// Use Next.js API route instead of direct backend call
const API_URL = "/api/check-scam";

export default function Home() {
  const [channel, setChannel] = useState<Channel>("voice");
  const [input, setInput] = useState("");
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [voiceFileName, setVoiceFileName] = useState("");
  const [imageFileName, setImageFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<ScanResult>({
    level: "pending",
    score: 0,
    reason: "Awaiting evidence. Paste a summary for voice, text, or image.",
    channel: "voice",
    timestamp: "",
  });
  const [history, setHistory] = useState<ScanResult[]>([]);
  
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // Initialize timestamp on client side only
  useEffect(() => {
    setStatus((prev) => ({
      ...prev,
      timestamp: getCurrentTimeString(),
    }));
  }, []);

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("authToken");
      const storedUser = localStorage.getItem("user");
      
      if (token && storedUser) {
        try {
          const response = await fetch(`/api/auth?action=check&token=${token}`);
          
          const contentType = response.headers.get("content-type");
          if (!contentType || !contentType.includes("application/json")) {
            // Backend returned HTML or other non-JSON, likely an error
            console.error("Auth check: Non-JSON response received");
            localStorage.removeItem("authToken");
            localStorage.removeItem("user");
            return;
          }
          
          const data = await response.json();
          
          if (data.authenticated) {
            setIsAuthenticated(true);
            setAuthToken(token);
            setUser(data.user || JSON.parse(storedUser));
          } else {
            // Token invalid, clear storage
            localStorage.removeItem("authToken");
            localStorage.removeItem("user");
          }
        } catch (err) {
          console.error("Auth check failed:", err);
          localStorage.removeItem("authToken");
          localStorage.removeItem("user");
        }
      }
      setCheckingAuth(false);
    };
    
    checkAuth();
  }, []);

  const handleAuthSuccess = (token: string, userData: { email: string; name: string }) => {
    setAuthToken(token);
    setUser(userData);
    setIsAuthenticated(true);
    setShowAuthModal(false);
  };

  const handleLogout = async () => {
    try {
      if (authToken) {
        await fetch("/api/auth", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "logout", token: authToken }),
        });
      }
    } catch (err) {
      console.error("Logout error:", err);
    }
    
    localStorage.removeItem("authToken");
    localStorage.removeItem("user");
    setAuthToken(null);
    setUser(null);
    setIsAuthenticated(false);
  };

  const riskTitle = useMemo(() => {
    if (status.level === "pending") return "No decision yet";
    if (status.level === "safe") return "Likely legitimate";
    if (status.level === "warn") return "Caution";
    return "High risk";
  }, [status.level]);

  const displayChannel = status.level === "pending" ? channel : status.channel;

  const scoreLabel = useMemo(
    () =>
      status.level === "pending"
        ? "Confidence"
        : `${status.score}% confidence · ${displayChannel.toUpperCase()} scan`,
    [status.score, status.level, displayChannel]
  );

  useEffect(() => {
    setInput("");
    setVoiceFile(null);
    setImageFile(null);
    setVoiceFileName("");
    setImageFileName("");
  }, [channel]);

  // Map API label to UI risk level
  const mapLabelToLevel = (label: string, riskScore: number): RiskLevel => {
    if (label === "scam" || riskScore >= 70) return "danger";
    if (label === "suspicious" || riskScore >= 40) return "warn";
    return "safe";
  };

  const runScan = async () => {
    // Check authentication for image/voice
    if ((channel === "voice" || channel === "image") && !isAuthenticated) {
      setShowAuthModal(true);
      setStatus((prev) => ({
        ...prev,
        level: "pending",
        score: 0,
        reason: "Please sign up or log in to use image and voice checking.",
        channel,
        timestamp: getCurrentTimeString(),
      }));
      return;
    }

    // Validate input
    if (channel === "text" && !input.trim()) {
      setStatus((prev) => ({
        ...prev,
        level: "pending",
        score: 0,
        reason: "Add evidence first — paste the transcript or summary.",
        channel,
        timestamp: getCurrentTimeString(),
      }));
      return;
    }

    if ((channel === "voice" || channel === "image") && !voiceFile && !imageFile && !input.trim()) {
      setStatus((prev) => ({
        ...prev,
        level: "pending",
        score: 0,
        reason: "Please upload a file or provide text input.",
        channel,
        timestamp: new Date().toLocaleTimeString(),
      }));
      return;
    }

    setLoading(true);
    setStatus((prev) => ({
      ...prev,
      level: "pending",
      score: 0,
      reason: "Analyzing...",
      channel,
      timestamp: getCurrentTimeString(),
    }));

    try {
      const formData = new FormData();
      formData.append("type", channel);

      // Handle different input types based on channel
      if (channel === "text") {
        // For text channel, send content
        if (input.trim()) {
          formData.append("content", input.trim());
        }
      } else if (channel === "voice") {
        // For voice channel, send file if available, otherwise send content as transcription
        if (voiceFile) {
          formData.append("file", voiceFile);
        } else if (input.trim()) {
          formData.append("content", input.trim());
        }
      } else if (channel === "image") {
        // For image channel, send file if available, otherwise send content as description
        if (imageFile) {
          formData.append("file", imageFile);
        } else if (input.trim()) {
          formData.append("content", input.trim());
        }
      }

      // Add auth token to form data if available
      if (authToken) {
        formData.append("token", authToken);
      }

      const headers: HeadersInit = {};
      if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
      }

      const response = await fetch(API_URL, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorData.message || errorMessage;
        } catch {
          // If response is not JSON, try to get text
          try {
            const errorText = await response.text();
            errorMessage = errorText || errorMessage;
          } catch {
            // Use default error message
            errorMessage = `Server error: ${response.status} ${response.statusText}`;
          }
        }
        throw new Error(errorMessage);
      }

      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        console.error("Failed to parse response as JSON:", parseError);
        throw new Error("Invalid response format from server. Please try again.");
      }

      // Map API response to UI format (Next.js API route format)
      const details = data.details || data;
      const riskLevel = mapLabelToLevel(details.label || "benign", details.risk_score || 0);
      const result: ScanResult = {
        level: riskLevel,
        score: details.risk_score || 0,
        reason: data.message || details.explanation || details.recommended_action || "Analysis complete.",
        channel,
        timestamp: getCurrentTimeString(),
      };

      setStatus(result);
      setHistory((prev) => [result, ...prev].slice(0, 5));

      // If audio URL is returned, you could play it here
      if (details.audio_url || details.audio_base64) {
        console.log("Audio available:", details.audio_url || "base64 encoded");
      }
    } catch (error) {
      console.error("Scan error:", error);
      const errorMessage = error instanceof Error 
        ? error.message 
        : typeof error === 'string' 
          ? error 
          : "Failed to analyze. Please try again.";
      
      // Handle auth errors - show login modal if auth required
      if (errorMessage.includes("Authentication required") || 
          errorMessage.includes("requiresAuth") ||
          errorMessage.includes("Invalid or expired token")) {
        setShowAuthModal(true);
        setIsAuthenticated(false);
        setAuthToken(null);
        setUser(null);
        localStorage.removeItem("authToken");
        localStorage.removeItem("user");
        setStatus((prev) => ({
          ...prev,
          level: "pending",
          score: 0,
          reason: "Please sign up or log in to use image and voice checking.",
          channel,
          timestamp: getCurrentTimeString(),
        }));
        setLoading(false);
        return;
      }
      
      // Truncate very long error messages for better UX
      const displayMessage = errorMessage.length > 200 
        ? errorMessage.substring(0, 200) + "..." 
        : errorMessage;
      
      setStatus({
        level: "pending",
        score: 0,
        reason: displayMessage,
        channel,
        timestamp: getCurrentTimeString(),
      });
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="min-h-screen bg-[#0c1018] text-slate-100">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-12">
        <header className="space-y-4 text-center">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-slate-200">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Scam Shield · Voice · Text · Image
            </div>
            <div className="flex items-center gap-3">
              {isAuthenticated && user ? (
                <>
                  <span className="text-sm text-slate-300">
                    {user.name || user.email}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-slate-100"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="rounded-lg bg-emerald-500/20 border border-emerald-500/50 px-3 py-1.5 text-xs font-medium text-emerald-300 transition hover:bg-emerald-500/30"
                >
                  Sign Up / Log In
                </button>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold md:text-4xl">
              What do you want to validate?
            </h1>
            <p className="text-sm text-slate-400 md:text-base">
              Text checking is free! Sign up to unlock image and voice file checking.
            </p>
          </div>
          <div className="flex justify-center">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2 py-1">
              {(["voice", "text", "image"] as Channel[]).map((c) => (
                <button
                  key={c}
                  onClick={() => setChannel(c)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition relative ${
                    channel === c
                      ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30"
                      : "text-slate-200 hover:bg-white/5"
                  }`}
                >
                  {channelCopy[c].label}
                  {(c === "voice" || c === "image") && !isAuthenticated && (
                    <span className="ml-1.5 text-[10px]">🔒</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </header>

        <section className="grid gap-6 md:grid-cols-[1.05fr,0.95fr]">
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg shadow-black/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
                    Evidence
                  </p>
                  <p className="text-sm text-slate-300">{channelCopy[channel].hint}</p>
                </div>
              </div>
              {channel === "voice" && (
                <>
                  {!isAuthenticated && (
                    <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                      <p className="font-semibold">🔒 Authentication Required</p>
                      <p className="mt-1 text-xs text-amber-300/80">
                        Voice file checking requires a free account. Click "Sign Up / Log In" above to get started.
                      </p>
                    </div>
                  )}
                  <label className={`mt-3 flex flex-col gap-2 rounded-xl border border-dashed px-4 py-4 text-sm text-slate-200 transition ${
                    isAuthenticated 
                      ? "border-emerald-400/60 bg-[#0f141f] hover:border-emerald-300 hover:bg-white/5" 
                      : "border-slate-600/40 bg-[#0a0d12] opacity-60 cursor-not-allowed"
                  }`}>
                    <input
                      type="file"
                      accept=".mp3,.wav,audio/*"
                      className="hidden"
                      disabled={!isAuthenticated}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setVoiceFile(file);
                          setVoiceFileName(file.name);
                        }
                      }}
                    />
                    <span className="text-slate-200">
                      {isAuthenticated ? "Upload or drop a .mp3 / .wav" : "🔒 Sign in to upload voice files"}
                    </span>
                    <span className="text-xs text-slate-400">
                      {isAuthenticated 
                        ? "Max a few MB. Optional: paste a short summary below."
                        : "Text checking is free. Sign up to unlock voice and image checking."}
                    </span>
                    {voiceFileName && (
                      <span className="text-xs text-emerald-200">Selected: {voiceFileName}</span>
                    )}
                  </label>
                </>
              )}
              {channel === "image" && (
                <>
                  {!isAuthenticated && (
                    <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                      <p className="font-semibold">🔒 Authentication Required</p>
                      <p className="mt-1 text-xs text-amber-300/80">
                        Image file checking requires a free account. Click "Sign Up / Log In" above to get started.
                      </p>
                    </div>
                  )}
                  <label className={`mt-3 flex flex-col gap-2 rounded-xl border border-dashed px-4 py-4 text-sm text-slate-200 transition ${
                    isAuthenticated 
                      ? "border-cyan-400/60 bg-[#0f141f] hover:border-cyan-300 hover:bg-white/5" 
                      : "border-slate-600/40 bg-[#0a0d12] opacity-60 cursor-not-allowed"
                  }`}>
                    <input
                      type="file"
                      accept="image/png,image/jpeg"
                      className="hidden"
                      disabled={!isAuthenticated}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setImageFile(file);
                          setImageFileName(file.name);
                        }
                      }}
                    />
                    <span className="text-slate-200">
                      {isAuthenticated ? "Drag in or upload a PNG / JPEG" : "🔒 Sign in to upload images"}
                    </span>
                    <span className="text-xs text-slate-400">
                      {isAuthenticated 
                        ? "Optional: add a short description below."
                        : "Text checking is free. Sign up to unlock voice and image checking."}
                    </span>
                    {imageFileName && (
                      <span className="text-xs text-cyan-200">Selected: {imageFileName}</span>
                    )}
                  </label>
                </>
              )}
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={channel === "text" ? 5 : 3}
                className="mt-3 w-full rounded-xl border border-white/10 bg-[#0f141f] px-3 py-3 text-sm text-slate-100 outline-none transition focus:border-emerald-400/70 focus:ring-2 focus:ring-emerald-400/30"
                placeholder={
                  channel === "voice"
                    ? "Optional summary or transcript to pair with the audio…"
                    : channel === "image"
                      ? "Optional description or OCR text from the image…"
                      : channelCopy[channel].placeholder
                }
              />
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 px-3 py-1">
                  AI ready
                </span>
                <span className="rounded-full border border-white/10 px-3 py-1">
                  Human override
                </span>
                <span className="rounded-full border border-white/10 px-3 py-1">
                  Quick audit
                </span>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button
                  onClick={runScan}
                  disabled={loading}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? "Analyzing..." : "Run scan"}
                </button>
              </div>
            </div>

            <div
              className={`rounded-2xl border p-5 shadow-lg shadow-black/20 transition ${riskPalette[status.level]}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-300">
                    AI outcome
                  </p>
                  <p className="text-sm text-slate-200">{scoreLabel}</p>
                </div>
                <span className="rounded-full border border-white/15 px-3 py-1 text-[11px] text-slate-200">
                  {status.timestamp} · {displayChannel.toUpperCase()}
                </span>
              </div>
              <h3 className={`mt-3 text-2xl font-semibold ${riskAccent[status.level]}`}>
                {riskTitle}
              </h3>
              <p className="mt-2 text-sm text-slate-200/90">{status.reason}</p>
              <div className="mt-4 flex items-center gap-3 text-[12px] text-slate-200">
                <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">
                    Confidence
                  </p>
                  <p className="text-sm font-semibold">{status.score || 0}%</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">
                    Channel
                  </p>
                  <p className="text-sm font-semibold capitalize">{status.channel}</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-slate-400">
                    Next step
                  </p>
                  <p className="text-sm font-semibold">
                    {status.level === "danger"
                      ? "Call back to verify"
                      : status.level === "warn"
                        ? "Secondary review"
                        : "Proceed"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-lg shadow-black/20">
            <div className="flex items-center justify-between">
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">
                Recent checks
              </p>
              <span className="text-xs text-slate-400">
                Last {history.length || 0} decisions
              </span>
            </div>
            {history.length === 0 ? (
              <p className="text-sm text-slate-300">
                No recent scans. Run an AI check to populate this list.
              </p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-200">
                {history.map((item, idx) => (
                  <li
                    key={`${item.timestamp}-${idx}`}
                    className="flex items-center justify-between rounded-lg border border-white/10 bg-[#0f141f] px-3 py-2"
                  >
                    <div className="flex flex-col">
                      <span className="font-semibold capitalize">
                        {item.channel} · {item.level}
                      </span>
                      <span className="text-xs text-slate-300">{item.reason}</span>
                    </div>
                    <span className="text-xs text-slate-300">
                      {item.score}% · {item.timestamp}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
      
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
