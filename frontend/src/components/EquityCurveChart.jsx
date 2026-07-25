import React, { useState, useEffect } from "react";

const EquityCurveChart = () => {
  const [range, setRange] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [curveData, setCurveData] = useState(null);

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchEquityCurve = async (selectedRange) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/analytics/equity-curve?range=${selectedRange}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error("Gagal mengambil data kurva ekuitas.");
      }

      const data = await res.json();
      setCurveData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEquityCurve(range);
  }, [range]);

  const summary = curveData?.summary || {
    current_balance: 0,
    unrealized_pnl: 0,
    total_deposits: 0,
    total_withdrawals: 0,
    net_transfers: 0,
    real_trading_profit: 0,
    trading_return_pct: 0,
  };

  const points = curveData?.data_points || [];

  // Helper to render SVG dual lines
  const renderSvgChart = () => {
    if (points.length === 0) return null;

    const width = 800;
    const height = 280;
    const padding = 40;

    const equityVals = points.map((p) => p.real_equity);
    const pnlVals = points.map((p) => p.cumulative_pnl);

    const minEq = Math.min(...equityVals, 0);
    const maxEq = Math.max(...equityVals, 10);
    const minPnl = Math.min(...pnlVals, 0);
    const maxPnl = Math.max(...pnlVals, 10);

    const eqRange = maxEq - minEq || 1;
    const pnlRange = maxPnl - minPnl || 1;

    const getEqY = (val) => height - padding - ((val - minEq) / eqRange) * (height - 2 * padding);
    const getPnlY = (val) => height - padding - ((val - minPnl) / pnlRange) * (height - 2 * padding);
    const getX = (idx) => padding + (idx / (points.length - 1 || 1)) * (width - 2 * padding);

    const eqPath = points.reduce((acc, p, idx) => {
      const x = getX(idx);
      const y = getEqY(p.real_equity);
      return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
    }, "");

    const pnlPath = points.reduce((acc, p, idx) => {
      const x = getX(idx);
      const y = getPnlY(p.cumulative_pnl);
      return idx === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
    }, "");

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={styles.svg}>
        <defs>
          <linearGradient id="eqGlow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.0" />
          </linearGradient>
          <linearGradient id="pnlGlow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.05)" />
        <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="rgba(255,255,255,0.05)" />
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.05)" />

        {/* Real Equity Line (Purple) */}
        <path d={eqPath} fill="none" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" />

        {/* Cumulative PnL Line (Green) */}
        <path d={pnlPath} fill="none" stroke="#10b981" strokeWidth="2.5" strokeDasharray="4 2" strokeLinecap="round" />

        {/* Data Point Circles */}
        {points.map((p, idx) => (
          <g key={idx}>
            <circle cx={getX(idx)} cy={getEqY(p.real_equity)} r="4" fill="#a78bfa" />
            <circle cx={getX(idx)} cy={getPnlY(p.cumulative_pnl)} r="3" fill="#10b981" />
          </g>
        ))}
      </svg>
    );
  };

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <h2 style={styles.cardTitle}>📈 Layanan Snapshot Ekuitas & Performance Growth</h2>
          <p style={styles.cardSubtitle}>
            Visualisasi kurva pertumbuhan saldo riil Binance vs kualitas keputusan trading murni (R-Kumulatif)
          </p>
        </div>

        {/* Timeframe Filters */}
        <div style={styles.filterGroup}>
          {[
            { id: "7d", label: "7 Hari" },
            { id: "30d", label: "30 Hari" },
            { id: "month", label: "Bulan Ini" },
            { id: "year", label: "Tahun Ini" },
            { id: "all", label: "Semua" },
          ].map((btn) => (
            <button
              key={btn.id}
              onClick={() => setRange(btn.id)}
              style={{
                ...styles.filterBtn,
                ...(range === btn.id ? styles.filterBtnActive : {}),
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Badge Cards */}
      <div style={styles.badgeGrid}>
        <div style={styles.badgeCard}>
          <span style={styles.badgeLabel}>SALDO REAL (BINANCE)</span>
          <span style={{ ...styles.badgeValue, color: "#ffffff" }}>
            ${summary.current_balance.toFixed(2)}
          </span>
          <span style={styles.badgeSub}>
            UnPnl: <b style={{ color: summary.unrealized_pnl >= 0 ? "#22c55e" : "#ef4444" }}>
              {summary.unrealized_pnl >= 0 ? `+$${summary.unrealized_pnl}` : `-$${Math.abs(summary.unrealized_pnl)}`}
            </b>
          </span>
        </div>

        <div style={styles.badgeCard}>
          <span style={styles.badgeLabel}>PROFIT TRADING RIIL</span>
          <span style={{ ...styles.badgeValue, color: summary.real_trading_profit >= 0 ? "#22c55e" : "#ef4444" }}>
            {summary.real_trading_profit >= 0 ? `+$${summary.real_trading_profit.toFixed(2)}` : `-$${Math.abs(summary.real_trading_profit).toFixed(2)}`}
          </span>
          <span style={styles.badgeSub}>
            Return: <b style={{ color: summary.trading_return_pct >= 0 ? "#22c55e" : "#ef4444" }}>
              {summary.trading_return_pct >= 0 ? `+${summary.trading_return_pct.toFixed(1)}%` : `${summary.trading_return_pct.toFixed(1)}%`}
            </b>
          </span>
        </div>

        <div style={styles.badgeCard}>
          <span style={styles.badgeLabel}>NET TRANSFER EKSTERNAL</span>
          <span style={{ ...styles.badgeValue, color: "#a78bfa" }}>
            ${summary.net_transfers.toFixed(2)}
          </span>
          <span style={styles.badgeSub}>
            Dep: <b>${summary.total_deposits}</b> | Wdr: <b>${summary.total_withdrawals}</b>
          </span>
        </div>
      </div>

      {/* Legend */}
      <div style={styles.legendRow}>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#a78bfa" }} />
          <span>🟣 <b>Saldo Real Equity ($)</b> — Pertumbuhan Akun setelah Net Transfer</span>
        </div>
        <div style={styles.legendItem}>
          <span style={{ ...styles.legendDot, backgroundColor: "#10b981" }} />
          <span>🟢 <b>Kumulatif Net PnL ($ / R)</b> — Kualitas Keputusan Trading Murni</span>
        </div>
      </div>

      {/* Chart Canvas Area */}
      <div style={styles.chartContainer}>
        {loading ? (
          <div style={styles.placeholderText}>⏳ Memuat data kurva ekuitas...</div>
        ) : error ? (
          <div style={styles.errorText}>⚠️ {error}</div>
        ) : points.length === 0 ? (
          <div style={styles.placeholderText}>Belum ada data ekuitas untuk periode ini.</div>
        ) : (
          renderSvgChart()
        )}
      </div>
    </div>
  );
};

const styles = {
  card: {
    backgroundColor: "rgba(22, 19, 39, 0.7)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: "16px",
    padding: "24px",
    marginBottom: "24px",
    backdropFilter: "blur(12px)",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
    marginBottom: "20px",
  },
  cardTitle: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#ffffff",
    margin: 0,
  },
  cardSubtitle: {
    fontSize: "13px",
    color: "#94a3b8",
    margin: "4px 0 0 0",
  },
  filterGroup: {
    display: "flex",
    gap: "6px",
    backgroundColor: "rgba(15, 12, 30, 0.8)",
    padding: "4px",
    borderRadius: "10px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
  },
  filterBtn: {
    backgroundColor: "transparent",
    border: "none",
    color: "#94a3b8",
    padding: "6px 14px",
    borderRadius: "7px",
    fontSize: "12px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  filterBtnActive: {
    backgroundColor: "rgba(124, 58, 237, 0.8)",
    color: "#ffffff",
  },
  badgeGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "14px",
    marginBottom: "20px",
  },
  badgeCard: {
    backgroundColor: "rgba(15, 12, 30, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    borderRadius: "12px",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  badgeLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: "0.5px",
  },
  badgeValue: {
    fontSize: "20px",
    fontWeight: "800",
  },
  badgeSub: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  legendRow: {
    display: "flex",
    gap: "20px",
    flexWrap: "wrap",
    marginBottom: "16px",
    fontSize: "12px",
    color: "#cbd5e1",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  legendDot: {
    width: "10px",
    height: "10px",
    borderRadius: "50%",
  },
  chartContainer: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: "12px",
    padding: "16px",
    minHeight: "280px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  svg: {
    width: "100%",
    height: "100%",
    maxHeight: "280px",
  },
  placeholderText: {
    color: "#64748b",
    fontSize: "14px",
  },
  errorText: {
    color: "#f87171",
    fontSize: "14px",
  },
};

export default EquityCurveChart;
