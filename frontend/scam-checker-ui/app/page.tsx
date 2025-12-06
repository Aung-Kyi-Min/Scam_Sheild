"use client";

import { useEffect, useMemo, useState } from "react";

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

const reasons = [
  "Detected urgency language and payment request without validation.",
  "Links redirect to non-official domains; sender spoofed.",
  "Audio pacing and metadata do not match expected caller profile.",
  "Visual signature mismatches known templates; potential tampering.",
  "Content is consistent with verified sender history.",
];

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

export default function Home() {
  const [channel, setChannel] = useState<Channel>("voice");
  const [input, setInput] = useState("");
  const [voiceFileName, setVoiceFileName] = useState("");
  const [imageFileName, setImageFileName] = useState("");
  const [status, setStatus] = useState<ScanResult>({
    level: "pending",
    score: 0,
    reason: "Awaiting evidence. Paste a summary for voice, text, or image.",
    channel: "voice",
    timestamp: new Date().toLocaleTimeString(),
  });
  const [history, setHistory] = useState<ScanResult[]>([]);

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
    setVoiceFileName("");
    setImageFileName("");
  }, [channel]);

  const runScan = () => {
    if (!input.trim()) {
      setStatus((prev) => ({
        ...prev,
        level: "pending",
        score: 0,
        reason: "Add evidence first — paste the transcript or summary.",
        channel,
        timestamp: new Date().toLocaleTimeString(),
      }));
      return;
    }

    const sampledLevel: RiskLevel =
      Math.random() > 0.65
        ? "danger"
        : Math.random() > 0.4
          ? "warn"
          : "safe";
    const sampledScore =
      sampledLevel === "danger"
        ? 92 + Math.round(Math.random() * 6)
        : sampledLevel === "warn"
          ? 68 + Math.round(Math.random() * 8)
          : 40 + Math.round(Math.random() * 12);

    const result: ScanResult = {
      level: sampledLevel,
      score: sampledScore,
      reason: reasons[Math.floor(Math.random() * reasons.length)],
      channel,
      timestamp: new Date().toLocaleTimeString(),
    };

    setStatus(result);
    setHistory((prev) => [result, ...prev].slice(0, 5));
  };

  const quickMark = (level: Exclude<RiskLevel, "pending">) => {
    const result: ScanResult = {
      level,
      score: level === "safe" ? 35 : level === "warn" ? 70 : 95,
      reason:
        level === "safe"
          ? "Manually marked as trusted after human verification."
          : level === "warn"
            ? "Pending more context; flagged for secondary review."
            : "Manual override: behavior matches known scam patterns.",
      channel,
      timestamp: new Date().toLocaleTimeString(),
    };
    setStatus(result);
    setHistory((prev) => [result, ...prev].slice(0, 5));
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
                        setVoiceFileName(file.name);
                        setInput(file.name);
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
                        setImageFileName(file.name);
                        setInput(file.name);
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
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition hover:brightness-110"
                >
                  Run scan
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
