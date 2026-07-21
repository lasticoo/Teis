import { useState, useEffect } from "react";

// ─── Helpers ──────────────────────────────────────────────────────────────────
const TREND_CONFIG = {
  bull: { label: "BULL 📈", color: "#22c55e", bg: "rgba(34,197,94,0.12)", border: "rgba(34,197,94,0.35)" },
  bear: { label: "BEAR 📉", color: "#ef4444", bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.35)" },
  range: { label: "RANGE ↔", color: "#f59e0b", bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.35)" },
};

const SESSION_CONFIG = {
  asia:     { label: "Asia 🌏", color: "#a78bfa" },
  london:   { label: "London 🇬🇧", color: "#60a5fa" },
  new_york: { label: "New York 🗽", color: "#34d399" },
};

function fgiLabel(value) {
  if (value <= 25)  return { label: "Extreme Fear 😱", color: "#ef4444" };
  if (value <= 45)  return { label: "Fear 😨", color: "#f97316" };
  if (value <= 55)  return { label: "Neutral 😐", color: "#f59e0b" };
  if (value <= 75)  return { label: "Greed 🤑", color: "#84cc16" };
  return                    { label: "Extreme Greed 🚀", color: "#22c55e" };
}

// ─── Sub‑components ───────────────────────────────────────────────────────────
function MetricRow({ label, value, unit = "", color }) {
  return (
    <div style={styles.metricRow}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={{ ...styles.metricValue, color: color || "#e2e8f0" }}>
        {value !== null && value !== undefined ? `${value}${unit}` : "—"}
      </span>
    </div>
  );
}



function TrendBadge({ label: trendKey }) {
  const cfg = TREND_CONFIG[trendKey] || TREND_CONFIG.range;
  return (
    <span style={{
      ...styles.badge,
      color: cfg.color,
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
    }}>
      {cfg.label}
    </span>
  );
}



function FearGreedBar({ value }) {
  if (value === null || value === undefined) return <span style={styles.metricValue}>—</span>;
  const { label, color } = fgiLabel(value);
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ ...styles.metricValue, color }}>{label}</span>
        <span style={{ ...styles.metricValue, color }}>{value} / 100</span>
      </div>
      <div style={styles.progressTrack}>
        <div style={{
          ...styles.progressFill,
          width: `${value}%`,
          background: `linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #22c55e 100%)`,
          backgroundSize: "200% 100%",
          backgroundPositionX: `${100 - value}%`,
        }} />
      </div>
    </div>
  );
}



// ─── Main Component ───────────────────────────────────────────────────────────
/**
 * MarketContextCard
 *
 * Displays the collected market context for a given trade.
 * Can either receive `contextData` directly as a prop (static mode)
 * or fetch it automatically from the backend using `tradeId` (dynamic mode).
 */
export default function MarketContextCard({ tradeId, contextData: propData = null }) {
  const [ctx, setCtx] = useState(propData);
  const [loading, setLoading] = useState(!propData);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (propData) {
      setCtx(propData);
      setLoading(false);
      return;
    }
    if (!tradeId) return;

    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    setLoading(true);
    fetch(`http://localhost:8000/api/v1/journal/trade/${tradeId}/context`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => { setCtx(data); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [tradeId, propData]);

  // ── Loading State ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={styles.card}>
        <div style={styles.header}>
          <span style={styles.headerIcon}>🌍</span>
          <h3 style={styles.headerTitle}>Konteks Pasar</h3>
        </div>
        <div style={styles.loadingState}>
          <div style={styles.spinner} />
          <p style={styles.loadingText}>Mengumpulkan data pasar…</p>
        </div>
      </div>
    );
  }

  // ── Error / Empty State ───────────────────────────────────────────────────
  if (error || !ctx) {
    return (
      <div style={styles.card}>
        <div style={styles.header}>
          <span style={styles.headerIcon}>🌍</span>
          <h3 style={styles.headerTitle}>Konteks Pasar</h3>
        </div>
        <div style={styles.emptyState}>
          <p style={styles.emptyText}>
            {error
              ? `Gagal memuat data: ${error}`
              : "Data konteks pasar belum tersedia. Akan otomatis terisi setelah Quick-Tag disimpan."}
          </p>
        </div>
      </div>
    );
  }

  // ── Data Ready ────────────────────────────────────────────────────────────
  const sessionCfg = SESSION_CONFIG[ctx.session] || { label: ctx.session || "—", color: "#94a3b8" };
  const capturedDate = ctx.captured_at
    ? new Date(ctx.captured_at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })
    : null;

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerIcon}>🌍</span>
        <h3 style={styles.headerTitle}>Konteks Pasar</h3>
        {capturedDate && <span style={styles.capturedAt}>Diambil: {capturedDate}</span>}
      </div>

      {/* Trend Section */}
      <div style={styles.section}>
        <p style={styles.sectionLabel}>TREND EMA50</p>
        <div style={styles.trendRow}>
          <div style={styles.trendCell}>
            <span style={styles.trendTimeframe}>HTF (4H)</span>
            <TrendBadge label={ctx.trend_htf} />
          </div>
          <div style={styles.trendDivider} />
          <div style={styles.trendCell}>
            <span style={styles.trendTimeframe}>LTF (1H)</span>
            <TrendBadge label={ctx.trend_ltf} />
          </div>
        </div>
      </div>

      <div style={styles.divider} />

      {/* Binance Metrics */}
      <div style={styles.section}>
        <p style={styles.sectionLabel}>METRIK BINANCE</p>
        <div style={styles.metricsGrid}>
          <MetricRow
            label="ATR‑14 (1H)"
            value={ctx.atr ? parseFloat(ctx.atr).toFixed(6) : null}
          />
          <MetricRow
            label="Volume 24H"
            value={ctx.volume_24h ? `$${Number(ctx.volume_24h).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : null}
          />
          <MetricRow
            label="Open Interest"
            value={ctx.open_interest ? `$${Number(ctx.open_interest).toLocaleString("en-US", { maximumFractionDigits: 0 })}` : null}
          />
          <MetricRow
            label="Funding Rate"
            value={ctx.funding_rate ? (parseFloat(ctx.funding_rate) * 100).toFixed(4) : null}
            unit="%"
            color={parseFloat(ctx.funding_rate) >= 0 ? "#22c55e" : "#ef4444"}
          />
          <MetricRow
            label="Sesi Trading"
            value={sessionCfg.label}
            color={sessionCfg.color}
          />
        </div>
      </div>

      <div style={styles.divider} />

      {/* Macro Section */}
      <div style={styles.section}>
        <p style={styles.sectionLabel}>INDIKATOR MAKRO</p>
        <div style={styles.metricsGrid}>
          <MetricRow
            label="BTC Dominance"
            value={ctx.btc_dominance ? parseFloat(ctx.btc_dominance).toFixed(2) : null}
            unit="%"
            color="#f59e0b"
          />
        </div>
        {/* Fear & Greed Bar */}
        <div style={{ marginTop: 12 }}>
          <span style={styles.metricLabel}>Fear &amp; Greed Index</span>
          <div style={{ marginTop: 8 }}>
            <FearGreedBar value={ctx.fear_greed_index} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  card: {
    background: "rgba(15,23,42,0.75)",
    backdropFilter: "blur(16px)",
    WebkitBackdropFilter: "blur(16px)",
    border: "1px solid rgba(99,102,241,0.25)",
    borderRadius: 16,
    padding: "20px 24px",
    color: "#e2e8f0",
    fontFamily: "'Inter', -apple-system, sans-serif",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  headerIcon: {
    fontSize: 20,
  },
  headerTitle: {
    margin: 0,
    fontSize: 15,
    fontWeight: 700,
    color: "#c7d2fe",
    flex: 1,
    letterSpacing: 0.3,
  },
  capturedAt: {
    fontSize: 11,
    color: "#64748b",
    fontStyle: "italic",
  },
  section: {
    marginBottom: 4,
  },
  sectionLabel: {
    margin: "0 0 10px",
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 1.2,
    color: "#475569",
    textTransform: "uppercase",
  },
  trendRow: {
    display: "flex",
    gap: 0,
    background: "rgba(255,255,255,0.03)",
    borderRadius: 10,
    overflow: "hidden",
    border: "1px solid rgba(255,255,255,0.07)",
  },
  trendCell: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 8,
    padding: "12px 8px",
  },
  trendDivider: {
    width: 1,
    background: "rgba(255,255,255,0.07)",
  },
  trendTimeframe: {
    fontSize: 11,
    color: "#64748b",
    fontWeight: 600,
    letterSpacing: 0.5,
  },
  badge: {
    padding: "4px 12px",
    borderRadius: 20,
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  divider: {
    height: 1,
    background: "rgba(255,255,255,0.06)",
    margin: "14px 0",
  },
  metricsGrid: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  metricRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metricLabel: {
    fontSize: 12,
    color: "#94a3b8",
    fontWeight: 500,
  },
  metricValue: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e2e8f0",
    fontVariantNumeric: "tabular-nums",
  },
  progressTrack: {
    height: 8,
    background: "rgba(255,255,255,0.08)",
    borderRadius: 4,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 4,
    transition: "width 0.6s ease",
  },
  loadingState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 12,
    padding: "24px 0",
  },
  spinner: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    border: "3px solid rgba(99,102,241,0.15)",
    borderTop: "3px solid #818cf8",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    margin: 0,
    fontSize: 13,
    color: "#64748b",
  },
  emptyState: {
    padding: "20px 0",
  },
  emptyText: {
    margin: 0,
    fontSize: 13,
    color: "#475569",
    textAlign: "center",
    lineHeight: 1.6,
  },
};
