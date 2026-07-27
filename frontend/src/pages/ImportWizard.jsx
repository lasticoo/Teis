import React, { useState, useRef, useEffect } from "react";
import { useAuth, API_URL } from "../context/AuthContext";

const WS_BASE = API_URL.replace(/^http/, "ws");

const today = () => new Date().toISOString().slice(0, 10);
const oneYearAgo = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  return d.toISOString().slice(0, 10);
};

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

  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  useEffect(() => () => wsRef.current?.close(), []);

  const addLog = (type, message) => {
    const ts = new Date().toLocaleTimeString();
    setLog((prev) => [...prev, { ts, type, message }]);
  };

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
      addLog("info", `🚀 Job impor dimulai — ID: ${newJobId}`);
    } catch (e) {
      setStatus("error");
      setErrMsg(e.message);
      return;
    }

    const wsUrl = `${WS_BASE}/import/ws/${newJobId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => addLog("info", "📡 WebSocket terhubung ke server import TEIS");

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.pct !== undefined) setProgress(data.pct);

        if (data.event === "started") {
          addLog("info", data.message || "Proses impor dimulai...");
        } else if (data.event === "progress") {
          addLog("progress", data.message);
        } else if (data.event === "complete") {
          setStatus("complete");
          setProgress(100);
          setSummary({
            fills: data.fills_found,
            trades: data.trades_saved,
            skipped: data.skipped,
            duration: data.duration_seconds,
          });
          addLog("success", data.message);
          ws.close();
        } else if (data.event === "error") {
          setStatus("error");
          setErrMsg(data.message);
          addLog("error", `❌ ${data.message}`);
          ws.close();
        }
      } catch (err) {
        console.error("WS Parse error", err);
      }
    };

    ws.onerror = () => {
      addLog("error", "⚠️ WebSocket error, mencoba sinkronisasi...");
    };

    ws.onclose = () => {
      addLog("info", "🔌 Koneksi WebSocket ditutup.");
    };
  };

  const handleReset = () => {
    wsRef.current?.close();
    setStatus("idle");
    setProgress(0);
    setLog([]);
    setSummary(null);
    setErrMsg("");
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Title Header */}
        <div style={styles.header}>
          <div>
            <h1 style={styles.title}>Wizard Impor Historis Binance Futures</h1>
            <span style={styles.subtitle}>
              Tarik riwayat transaksi Binance Futures masa lalu untuk membangun baseline performa analitis
            </span>
          </div>
        </div>

        {/* Info Box */}
        <div style={styles.infoBox}>
          <div style={styles.infoIcon}>💡</div>
          <div style={styles.infoText}>
            Proses impor membaca log fill <code style={styles.code}>userTrades</code> secara aman & idempotensial.
            Sistem secara otomatis mengabaikan fill duplikat untuk menjaga keakuratan statistik Win Rate & Expectancy.
          </div>
        </div>

        {/* Date Form Card */}
        <div style={styles.card}>
          <h3 style={styles.cardTitle}>📅 Rentang Waktu Impor</h3>
          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>TANGGAL MULAI</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={status === "running"}
                style={styles.input}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>TANGGAL SELESAI</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={status === "running"}
                style={styles.input}
              />
            </div>
          </div>

          {errMsg && (
            <div style={styles.errorBox}>
              ⚠️ {errMsg}
            </div>
          )}

          <div style={styles.btnRow}>
            {status === "idle" && (
              <button onClick={handleStart} style={styles.btnPrimary}>
                🚀 Mulai Impor Binance
              </button>
            )}
            {status === "running" && (
              <button disabled style={{ ...styles.btnPrimary, opacity: 0.6, cursor: "not-allowed" }}>
                ⏳ Memproses Impor ({progress}%)...
              </button>
            )}
            {(status === "complete" || status === "error") && (
              <button onClick={handleReset} style={styles.btnSecondary}>
                🔄 Impor Lagi / Reset
              </button>
            )}
          </div>
        </div>

        {/* Progress & Live Log Stream */}
        {status !== "idle" && (
          <div style={styles.card}>
            <div style={styles.progressHeader}>
              <span style={{ fontSize: "14px", fontWeight: "700", color: "#f8fafc" }}>
                {status === "running" ? "⚡ Memproses Data Binance..." : status === "complete" ? "✅ Impor Selesai!" : "❌ Impor Terhenti"}
              </span>
              <span style={styles.pctLabel}>{progress}%</span>
            </div>

            <div style={styles.progressTrack}>
              <div
                style={{
                  ...styles.progressFill,
                  width: `${progress}%`,
                  backgroundColor: status === "error" ? "#ef4444" : status === "complete" ? "#22c55e" : "#8b5cf6",
                }}
              />
            </div>

            {/* Summary Result */}
            {summary && (
              <div style={styles.summaryGrid}>
                <div style={styles.summaryCard}>
                  <span style={styles.summaryValue}>{summary.trades}</span>
                  <span style={styles.summaryLabel}>TRADE BARU</span>
                </div>
                <div style={styles.summaryCard}>
                  <span style={styles.summaryValue}>{summary.fills}</span>
                  <span style={styles.summaryLabel}>FILL DISIMPAN</span>
                </div>
                <div style={styles.summaryCard}>
                  <span style={{ ...styles.summaryValue, color: "#fbbf24" }}>{summary.skipped}</span>
                  <span style={styles.summaryLabel}>DUPLIKAT (DILEWATI)</span>
                </div>
                <div style={styles.summaryCard}>
                  <span style={{ ...styles.summaryValue, color: "#38bdf8" }}>{summary.duration}s</span>
                  <span style={styles.summaryLabel}>DURASI WAKTU</span>
                </div>
              </div>
            )}

            {/* Live Terminal Log */}
            <h4 style={{ margin: "20px 0 10px 0", fontSize: "13px", color: "#94a3b8" }}>💻 Live Execution Stream:</h4>
            <div style={styles.logContainer}>
              {log.map((entry, idx) => (
                <div key={idx} style={styles.logLine}>
                  <span style={styles.logTs}>[{entry.ts}]</span>
                  <span
                    style={{
                      color:
                        entry.type === "error"
                          ? "#ef4444"
                          : entry.type === "success"
                          ? "#22c55e"
                          : entry.type === "progress"
                          ? "#38bdf8"
                          : "#c4b5fd",
                    }}
                  >
                    {entry.message}
                  </span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0b0e11",
    color: "#e2e8f0",
    padding: "0",
  },
  content: {
    maxWidth: "900px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    margin: 0,
    fontSize: "24px",
    fontWeight: "800",
    color: "#ffffff",
  },
  subtitle: {
    fontSize: "13px",
    color: "#64748b",
  },
  infoBox: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "12px",
    padding: "16px",
    display: "flex",
    gap: "12px",
    alignItems: "flex-start",
  },
  infoIcon: {
    fontSize: "18px",
  },
  infoText: {
    fontSize: "13px",
    color: "#94a3b8",
    lineHeight: "1.5",
  },
  code: {
    backgroundColor: "rgba(124, 58, 237, 0.2)",
    color: "#c4b5fd",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "12px",
  },
  card: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "14px",
    padding: "24px",
  },
  cardTitle: {
    margin: "0 0 16px 0",
    fontSize: "16px",
    fontWeight: "700",
    color: "#f8fafc",
  },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
    gap: "16px",
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  label: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: "0.5px",
  },
  input: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e293b",
    color: "#f8fafc",
    padding: "10px 14px",
    borderRadius: "10px",
    fontSize: "13.5px",
    outline: "none",
  },
  errorBox: {
    marginTop: "16px",
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    color: "#f87171",
    padding: "12px 16px",
    borderRadius: "10px",
    fontSize: "13px",
  },
  btnRow: {
    marginTop: "20px",
    display: "flex",
    gap: "12px",
  },
  btnPrimary: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: "10px",
    padding: "12px 24px",
    fontSize: "13.5px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(124, 58, 237, 0.4)",
  },
  btnSecondary: {
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    color: "#e2e8f0",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "12px 24px",
    fontSize: "13.5px",
    fontWeight: "600",
    cursor: "pointer",
  },
  progressHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },
  pctLabel: {
    fontSize: "20px",
    fontWeight: "800",
    color: "#a78bfa",
  },
  progressTrack: {
    height: "10px",
    backgroundColor: "#0b0e11",
    borderRadius: "5px",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: "5px",
    transition: "width 0.4s ease",
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: "12px",
    marginTop: "20px",
  },
  summaryCard: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "10px",
    padding: "16px",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  summaryValue: {
    fontSize: "22px",
    fontWeight: "800",
    color: "#22c55e",
  },
  summaryLabel: {
    fontSize: "10.5px",
    fontWeight: "700",
    color: "#64748b",
  },
  logContainer: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "14px",
    maxHeight: "240px",
    overflowY: "auto",
    fontFamily: "monospace",
    fontSize: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  logLine: {
    display: "flex",
    gap: "10px",
  },
  logTs: {
    color: "#64748b",
  },
};
