"use client";

import { useEffect, useMemo, useState } from "react";

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
    // Leave empty on first render so SSR and client markup match; fill in on interactions
    timestamp: "",
  });
  const [history, setHistory] = useState<ScanResult[]>([]);

  // Initialize timestamp on client side only
  useEffect(() => {
    setStatus((prev) => ({
      ...prev,
      timestamp: getCurrentTimeString(),
    }));
  }, []);

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

      const response = await fetch(API_URL, {
        method: "POST",
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
      setStatus({
        level: "pending",
        score: 0,
        reason: error instanceof Error ? error.message : "Failed to analyze. Please try again.",
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
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-slate-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Scam Shield · Voice · Text · Image
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold md:text-4xl">
              What do you want to validate?
            </h1>
            <p className="text-sm text-slate-400 md:text-base">
              Paste notes, text, or image description. Pick a mode and get an instant read on safety.
            </p>
          </div>
          <div className="flex justify-center">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-2 py-1">
              {(["voice", "text", "image"] as Channel[]).map((c) => (
                <button
                  key={c}
                  onClick={() => setChannel(c)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    channel === c
                      ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30"
                      : "text-slate-200 hover:bg-white/5"
                  }`}
                >
                  {channelCopy[c].label}
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
                <label className="mt-3 flex flex-col gap-2 rounded-xl border border-dashed border-emerald-400/60 bg-[#0f141f] px-4 py-4 text-sm text-slate-200 transition hover:border-emerald-300 hover:bg-white/5">
                  <input
                    type="file"
                    accept=".mp3,.wav,audio/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setVoiceFile(file);
                        setVoiceFileName(file.name);
                      }
                    }}
                  />
                  <span className="text-slate-200">Upload or drop a .mp3 / .wav</span>
                  <span className="text-xs text-slate-400">
                    Max a few MB. Optional: paste a short summary below.
                  </span>
                  {voiceFileName && (
                    <span className="text-xs text-emerald-200">Selected: {voiceFileName}</span>
                  )}
                </label>
              )}
              {channel === "image" && (
                <label className="mt-3 flex flex-col gap-2 rounded-xl border border-dashed border-cyan-400/60 bg-[#0f141f] px-4 py-4 text-sm text-slate-200 transition hover:border-cyan-300 hover:bg-white/5">
                  <input
                    type="file"
                    accept="image/png,image/jpeg"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setImageFile(file);
                        setImageFileName(file.name);
                      }
                    }}
                  />
                  <span className="text-slate-200">Drag in or upload a PNG / JPEG</span>
                  <span className="text-xs text-slate-400">
                    Optional: add a short description below.
                  </span>
                  {imageFileName && (
                    <span className="text-xs text-cyan-200">Selected: {imageFileName}</span>
                  )}
                </label>
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
    </div>
  );
}
