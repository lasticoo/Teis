import React, { useState, useRef, useEffect } from "react";
import { useAuth, API_URL } from "../context/AuthContext";

// ─── Helpers ───────────────────────────────────────────────────────────────
const WS_BASE = API_URL.replace(/^http/, "ws");

const today = () => new Date().toISOString().slice(0, 10);
const oneYearAgo = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  return d.toISOString().slice(0, 10);
};

// ─── Component ─────────────────────────────────────────────────────────────
export default function ImportWizard() {
  const { token } = useAuth();

  const [startDate, setStartDate] = useState(oneYearAgo());
  const [endDate, setEndDate] = useState(today());
  const [status, setStatus] = useState("idle"); // idle | running | complete | error
  const [progress, setProgress] = useState(0);
  const [log, setLog] = useState([]);
  const [summary, setSummary] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [errMsg, setErrMsg] = useState("");

  const wsRef = useRef(null);
  const logEndRef = useRef(null);

  // Auto-scroll log
  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  // Cleanup WS on unmount
  useEffect(() => () => wsRef.current?.close(), []);

  // ── Start Import ──────────────────────────────────────────────────────────
  const handleStart = async () => {
    if (!startDate || !endDate) return;
    if (startDate > endDate) {
      setErrMsg("Tanggal mulai harus sebelum tanggal selesai.");
      return;
    }

    setStatus("running");
    setProgress(0);
    setLog([]);
    setSummary(null);
    setErrMsg("");

    // 1. POST to backend to queue the job
    let newJobId;
    try {
      const res = await fetch(`${API_URL}/import/binance`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ start_date: startDate, end_date: endDate }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Gagal memulai import.");
      }
      const data = await res.json();
      newJobId = data.job_id;
      setJobId(newJobId);
      addLog("info", `🚀 Job dimulai — ID: ${newJobId}`);
    } catch (e) {
      setStatus("error");
      setErrMsg(e.message);
      return;
    }

    // 2. Connect WebSocket for real-time progress
    const wsUrl = `${WS_BASE}/import/ws/${newJobId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => addLog("info", "📡 Terhubung ke stream progres…");

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        handleProgressEvent(data);
      } catch (_) {}
    };

    ws.onerror = () => {
      addLog("error", "⚠️ Koneksi WebSocket terputus. Proses tetap berjalan di server.");
    };

    ws.onclose = () => {
      if (status !== "complete" && status !== "error") {
        addLog("warn", "🔌 WebSocket ditutup.");
      }
    };
  };

  const handleProgressEvent = (data) => {
    const { event, pct, fills_found, trades_saved, skipped, current_symbol, message, duration_seconds } = data;

    if (event === "progress") {
      setProgress(pct);
      addLog("info", `${message}`);
    } else if (event === "started") {
      addLog("info", message);
    } else if (event === "complete") {
      setProgress(100);
      setStatus("complete");
      setSummary({ fills_found, trades_saved, skipped, duration_seconds });
      addLog("success", message);
      wsRef.current?.close();
    } else if (event === "error") {
      setStatus("error");
      setErrMsg(message);
      addLog("error", message);
      wsRef.current?.close();
    }
  };

  const addLog = (type, text) => {
    const ts = new Date().toLocaleTimeString("id-ID", { timeZone: "Asia/Jakarta" });
    setLog((prev) => [...prev.slice(-199), { type, text, ts }]);
  };

  const handleReset = () => {
    wsRef.current?.close();
    setStatus("idle");
    setProgress(0);
    setLog([]);
    setSummary(null);
    setJobId(null);
    setErrMsg("");
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      {/* Ambient glow */}
      <div style={s.glowTop} />
      <div style={s.glowBottom} />

      <div style={s.container}>
        {/* Header */}
        <div style={s.header}>
          <div style={s.headerIcon}>📥</div>
          <div>
            <h1 style={s.title}>Wizard Impor Historis</h1>
            <p style={s.subtitle}>
              Tarik riwayat trade Binance Futures masa lalu untuk membangun baseline performa awal.
            </p>
          </div>
          <div style={s.badge}>Fitur 9</div>
        </div>

        {/* Info Box */}
        <div style={s.infoBox}>
          <span style={s.infoIcon}>ℹ️</span>
          <div>
            <strong>Tentang Import Historis</strong>
            <p style={s.infoText}>
              Hanya data <strong>objektif</strong> (pair, harga, PnL, fee) yang diimpor. Data subjektif
              (setup, emosi, bias) sengaja dikosongkan untuk mencegah <em>hindsight bias</em>.
              Trade hasil impor ditandai <code style={s.code}>historical_import</code> dan dikecualikan
              dari kalkulasi Edge Discovery.
            </p>
          </div>
        </div>

        {/* Form */}
        <div style={s.card}>
          <h2 style={s.cardTitle}>⚙️ Konfigurasi Rentang Impor</h2>

          <div style={s.formGrid}>
            <div style={s.formGroup}>
              <label style={s.label}>📅 Tanggal Mulai</label>
              <input
                type="date"
                value={startDate}
                max={today()}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={status === "running"}
                style={s.input}
              />
            </div>
            <div style={s.formGroup}>
              <label style={s.label}>📅 Tanggal Selesai</label>
              <input
                type="date"
                value={endDate}
                max={today()}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={status === "running"}
                style={s.input}
              />
            </div>
          </div>

          {errMsg && (
            <div style={s.errorBox}>
              <span>⚠️</span> {errMsg}
            </div>
          )}

          <div style={s.btnRow}>
            {status === "idle" || status === "error" ? (
              <button
                onClick={handleStart}
                style={s.btnPrimary}
                onMouseOver={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
                onMouseOut={(e) => (e.currentTarget.style.transform = "none")}
              >
                🚀 Import Riwayat
              </button>
            ) : status === "running" ? (
              <button style={{ ...s.btnPrimary, ...s.btnDisabled }} disabled>
                <span style={s.spinner} /> Mengimpor…
              </button>
            ) : (
              <button
                onClick={handleReset}
                style={s.btnSecondary}
                onMouseOver={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
                onMouseOut={(e) => (e.currentTarget.style.transform = "none")}
              >
                🔄 Import Ulang
              </button>
            )}
          </div>
        </div>

        {/* Progress Section */}
        {(status === "running" || status === "complete") && (
          <div style={s.card}>
            <div style={s.progressHeader}>
              <h2 style={s.cardTitle}>
                {status === "running" ? "⏳ Progres Import" : "✅ Import Selesai"}
              </h2>
              <span style={s.pctLabel}>{progress}%</span>
            </div>

            {/* Progress Bar */}
            <div style={s.progressTrack}>
              <div
                style={{
                  ...s.progressFill,
                  width: `${progress}%`,
                  background:
                    status === "complete"
                      ? "linear-gradient(90deg, #10b981, #059669)"
                      : "linear-gradient(90deg, #8b5cf6, #a78bfa, #8b5cf6)",
                  backgroundSize: status === "running" ? "200% auto" : undefined,
                  animation: status === "running" ? "shimmer 2s linear infinite" : undefined,
                }}
              />
            </div>

            {/* Summary Cards */}
            {summary && (
              <div style={s.summaryGrid}>
                <SummaryCard emoji="📊" label="Trade Tersimpan" value={summary.trades_saved} color="#8b5cf6" />
                <SummaryCard emoji="📋" label="Fill Ditemukan" value={summary.fills_found} color="#06b6d4" />
                <SummaryCard emoji="⏭️" label="Duplikat Dilewati" value={summary.skipped} color="#f59e0b" />
                <SummaryCard emoji="⏱️" label="Durasi" value={`${summary.duration_seconds}s`} color="#10b981" />
              </div>
            )}
          </div>
        )}

        {/* Live Log */}
        {log.length > 0 && (
          <div style={s.card}>
            <h2 style={s.cardTitle}>📝 Log Real-Time</h2>
            <div style={s.logContainer}>
              {log.map((entry, i) => (
                <div key={i} style={{ ...s.logLine, color: logColor(entry.type) }}>
                  <span style={s.logTs}>[{entry.ts}]</span>
                  <span>{entry.text}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        )}

        {/* Footer Note */}
        <div style={s.footerNote}>
          <span>🔒</span>
          <span>
            Import berjalan di <strong>background server</strong>. Anda bisa menutup halaman ini — proses
            akan tetap berjalan dan trade akan muncul di{" "}
            <a href="/journal" style={s.link}>Jurnal</a> setelah selesai.
          </span>
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% center; }
          100% { background-position: -200% center; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        input[type="date"]::-webkit-calendar-picker-indicator {
          filter: invert(0.7);
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}

// ── Sub-component ─────────────────────────────────────────────────────────
function SummaryCard({ emoji, label, value, color }) {
  return (
    <div style={{ ...s.summaryCard, borderColor: color }}>
      <div style={{ fontSize: "1.5rem" }}>{emoji}</div>
      <div style={{ ...s.summaryValue, color }}>{value}</div>
      <div style={s.summaryLabel}>{label}</div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────
const logColor = (type) => {
  if (type === "error") return "#f87171";
  if (type === "success") return "#34d399";
  if (type === "warn") return "#fbbf24";
  return "#a5b4fc";
};

// ── Styles ────────────────────────────────────────────────────────────────
const s = {
  page: {
    position: "relative",
    minHeight: "calc(100vh - 70px)",
    backgroundColor: "#0d0a1b",
    padding: "2rem",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    overflowX: "hidden",
  },
  glowTop: {
    position: "fixed",
    top: "-100px",
    left: "50%",
    transform: "translateX(-50%)",
    width: "600px",
    height: "400px",
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  glowBottom: {
    position: "fixed",
    bottom: "-80px",
    right: "10%",
    width: "400px",
    height: "300px",
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  container: {
    maxWidth: "860px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    paddingBottom: "1rem",
    borderBottom: "1px solid rgba(139,92,246,0.2)",
  },
  headerIcon: {
    fontSize: "2.5rem",
    background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  title: {
    margin: 0,
    fontSize: "1.6rem",
    fontWeight: 800,
    background: "linear-gradient(135deg, #c4b5fd, #67e8f9)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  subtitle: {
    margin: "0.25rem 0 0",
    fontSize: "0.9rem",
    color: "#6b7280",
  },
  badge: {
    marginLeft: "auto",
    padding: "4px 12px",
    borderRadius: "20px",
    background: "rgba(139,92,246,0.2)",
    border: "1px solid rgba(139,92,246,0.4)",
    color: "#a78bfa",
    fontSize: "0.75rem",
    fontWeight: 700,
    letterSpacing: "1px",
    whiteSpace: "nowrap",
  },
  infoBox: {
    display: "flex",
    gap: "1rem",
    alignItems: "flex-start",
    background: "rgba(6,182,212,0.06)",
    border: "1px solid rgba(6,182,212,0.2)",
    borderRadius: "12px",
    padding: "1rem 1.25rem",
  },
  infoIcon: { fontSize: "1.3rem", flexShrink: 0 },
  infoText: {
    margin: "0.25rem 0 0",
    fontSize: "0.85rem",
    color: "#94a3b8",
    lineHeight: 1.7,
  },
  code: {
    background: "rgba(139,92,246,0.2)",
    color: "#c4b5fd",
    borderRadius: "4px",
    padding: "1px 5px",
    fontSize: "0.8rem",
    fontFamily: "monospace",
  },
  card: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(139,92,246,0.15)",
    borderRadius: "16px",
    padding: "1.5rem",
    backdropFilter: "blur(10px)",
  },
  cardTitle: {
    margin: "0 0 1.25rem",
    fontSize: "1rem",
    fontWeight: 700,
    color: "#e2e8f0",
  },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "1rem",
  },
  formGroup: { display: "flex", flexDirection: "column", gap: "6px" },
  label: { fontSize: "0.8rem", color: "#94a3b8", fontWeight: 600, letterSpacing: "0.5px" },
  input: {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(139,92,246,0.3)",
    borderRadius: "8px",
    color: "#e2e8f0",
    padding: "10px 14px",
    fontSize: "0.95rem",
    outline: "none",
    transition: "border-color 0.2s",
    colorScheme: "dark",
  },
  errorBox: {
    marginTop: "1rem",
    padding: "10px 14px",
    background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.3)",
    borderRadius: "8px",
    color: "#f87171",
    fontSize: "0.85rem",
    display: "flex",
    gap: "8px",
    alignItems: "center",
  },
  btnRow: { marginTop: "1.5rem", display: "flex", gap: "12px" },
  btnPrimary: {
    padding: "12px 28px",
    background: "linear-gradient(135deg, #7c3aed, #8b5cf6)",
    color: "#fff",
    border: "none",
    borderRadius: "10px",
    fontWeight: 700,
    fontSize: "0.95rem",
    cursor: "pointer",
    transition: "transform 0.2s, box-shadow 0.2s",
    boxShadow: "0 4px 20px rgba(139,92,246,0.4)",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  btnSecondary: {
    padding: "12px 28px",
    background: "transparent",
    color: "#a78bfa",
    border: "1px solid rgba(139,92,246,0.4)",
    borderRadius: "10px",
    fontWeight: 700,
    fontSize: "0.95rem",
    cursor: "pointer",
    transition: "transform 0.2s",
  },
  btnDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
    transform: "none !important",
  },
  spinner: {
    display: "inline-block",
    width: "14px",
    height: "14px",
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  progressHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" },
  pctLabel: {
    fontSize: "1.5rem",
    fontWeight: 800,
    background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  progressTrack: {
    height: "10px",
    borderRadius: "99px",
    background: "rgba(255,255,255,0.08)",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: "99px",
    transition: "width 0.5s ease",
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: "1rem",
    marginTop: "1.5rem",
  },
  summaryCard: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid",
    borderRadius: "12px",
    padding: "1rem",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "4px",
  },
  summaryValue: {
    fontSize: "1.6rem",
    fontWeight: 800,
  },
  summaryLabel: {
    fontSize: "0.75rem",
    color: "#6b7280",
    fontWeight: 600,
  },
  logContainer: {
    background: "rgba(0,0,0,0.4)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: "10px",
    padding: "1rem",
    maxHeight: "280px",
    overflowY: "auto",
    fontFamily: "monospace",
    fontSize: "0.78rem",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  logLine: { display: "flex", gap: "10px", alignItems: "flex-start" },
  logTs: { color: "#4b5563", flexShrink: 0 },
  footerNote: {
    display: "flex",
    gap: "10px",
    alignItems: "flex-start",
    padding: "1rem 1.25rem",
    background: "rgba(139,92,246,0.05)",
    border: "1px solid rgba(139,92,246,0.1)",
    borderRadius: "12px",
    fontSize: "0.82rem",
    color: "#64748b",
    lineHeight: 1.6,
  },
  link: { color: "#8b5cf6", textDecoration: "none" },
};
