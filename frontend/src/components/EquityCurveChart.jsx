import React, { useState, useEffect, useRef } from "react";

const EquityCurveChart = () => {
  const [range, setRange] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [curveData, setCurveData] = useState(null);
  const [hoverPoint, setHoverPoint] = useState(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const svgRef = useRef(null);
  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchEquityCurve = async (selectedRange, silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/analytics/equity-curve?range=${selectedRange}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error("Gagal mengambil data PnL ekuitas.");
      }

      const data = await res.json();
      setCurveData(data);
      setLastUpdated(new Date());
    } catch (err) {
      if (!silent) setError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // Initial fetch and 15s real-time interval
  useEffect(() => {
    fetchEquityCurve(range, false);

    const interval = setInterval(() => {
      fetchEquityCurve(range, true);
    }, 15000); // 15 seconds real-time polling

    return () => clearInterval(interval);
  }, [range]);

  const summary = curveData?.summary || {
    current_balance: 95.14,
    futures_balance: 5.14,
    funding_balance: 90.0,
    spot_balance: 0.0,
    unrealized_pnl: 0.0,
    total_deposits: 0.0,
    total_withdrawals: 0.0,
    net_transfers: 0.0,
    real_trading_profit: 0.0,
    trading_return_pct: 0.0,
    max_drawdown_pct: 0.0,
    win_days: 0,
    loss_days: 0,
    daily_avg_pnl: 0.0,
  };

  const points = curveData?.data_points || [];

  // Helper for mouse move crosshair on SVG
  const handleMouseMove = (e) => {
    if (!svgRef.current || points.length === 0) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;

    const width = rect.width;
    const padding = 40;
    const chartWidth = width - 2 * padding;

    // Find nearest point
    const step = chartWidth / (points.length - 1 || 1);
    let nearestIdx = Math.round((mouseX - padding) / step);
    if (nearestIdx < 0) nearestIdx = 0;
    if (nearestIdx >= points.length) nearestIdx = points.length - 1;

    const pt = points[nearestIdx];
    const ptX = padding + nearestIdx * step;

    setHoverPoint(pt);
    setHoverPos({ x: ptX, y: e.clientY - rect.top });
  };

  const handleMouseLeave = () => {
    setHoverPoint(null);
  };

  // Render Bezier Spline Curve
  const renderSvgChart = () => {
    if (points.length === 0) return null;

    const width = 800;
    const height = 300;
    const padding = 40;

    const pnlVals = points.map((p) => p.cumulative_pnl);
    const minPnl = Math.min(...pnlVals, 0);
    const maxPnl = Math.max(...pnlVals, 1);
    const pnlRange = maxPnl - minPnl || 1;

    const getX = (idx) => padding + (idx / (points.length - 1 || 1)) * (width - 2 * padding);
    const getY = (val) => height - padding - ((val - minPnl) / pnlRange) * (height - 2 * padding);

    // Build smooth path
    let pathD = "";
    points.forEach((p, idx) => {
      const x = getX(idx);
      const y = getY(p.cumulative_pnl);
      if (idx === 0) {
        pathD += `M ${x} ${y}`;
      } else {
        const prevX = getX(idx - 1);
        const prevY = getY(points[idx - 1].cumulative_pnl);
        const cp1x = prevX + (x - prevX) / 2;
        const cp2x = prevX + (x - prevX) / 2;
        pathD += ` C ${cp1x} ${prevY}, ${cp2x} ${y}, ${x} ${y}`;
      }
    });

    // Area fill path
    const areaD = `${pathD} L ${getX(points.length - 1)} ${height - padding} L ${getX(0)} ${height - padding} Z`;

    const isProfit = summary.real_trading_profit >= 0;
    const strokeColor = isProfit ? "#0ecb81" : "#f6465d";

    return (
      <div style={{ position: "relative" }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          style={styles.svg}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="pnlBinanceGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={strokeColor} stopOpacity="0.35" />
              <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="#2b313a" strokeWidth="1" strokeDasharray="3 3" />
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="#2b313a" strokeWidth="1" strokeDasharray="3 3" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#2b313a" strokeWidth="1" />

          {/* Area Fill */}
          <path d={areaD} fill="url(#pnlBinanceGlow)" />

          {/* Line Curve */}
          <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

          {/* Crosshair Cursor */}
          {hoverPoint && (
            <g>
              {/* Vertical line */}
              <line
                x1={hoverPos.x}
                y1={padding}
                x2={hoverPos.x}
                y2={height - padding}
                stroke="#848e9c"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              {/* Point Indicator */}
              <circle
                cx={hoverPos.x}
                cy={getY(hoverPoint.cumulative_pnl)}
                r="6"
                fill={strokeColor}
                stroke="#181a20"
                strokeWidth="2"
              />
            </g>
          )}
        </svg>

        {/* Floating Binance Crosshair Tooltip */}
        {hoverPoint && (
          <div
            style={{
              ...styles.tooltip,
              left: Math.min(Math.max(hoverPos.x, 120), 680),
              top: "10px",
            }}
          >
            <div style={styles.tooltipHeader}>
              <span>{new Date(hoverPoint.timestamp).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })} WIB</span>
              <span style={{ color: "#848e9c", fontSize: "11px" }}>{hoverPoint.label}</span>
            </div>
            <div style={styles.tooltipRow}>
              <span>Kumulatif PnL:</span>
              <b style={{ color: hoverPoint.cumulative_pnl >= 0 ? "#0ecb81" : "#f6465d" }}>
                {hoverPoint.cumulative_pnl >= 0 ? `+$${hoverPoint.cumulative_pnl}` : `-$${Math.abs(hoverPoint.cumulative_pnl)}`}
                {" "}
                ({hoverPoint.cumulative_pnl_pct >= 0 ? `+${hoverPoint.cumulative_pnl_pct}%` : `${hoverPoint.cumulative_pnl_pct}%`})
              </b>
            </div>
            <div style={styles.tooltipRow}>
              <span>Net Asset Value (NAV):</span>
              <b style={{ color: "#ea6e00" }}>${hoverPoint.real_equity}</b>
            </div>
          </div>
        )}
      </div>
    );
  };

  const isProfit = summary.real_trading_profit >= 0;
  const mainColor = isProfit ? "#0ecb81" : "#f6465d";

  return (
    <div style={styles.container}>
      {/* Top Banner Header */}
      <div style={styles.header}>
        <div style={styles.titleGroup}>
          <div style={styles.titleRow}>
            <h2 style={styles.title}>Analisis PnL Akun (Binance Mobile Style)</h2>
            <span style={styles.liveBadge}>
              <span style={styles.liveDot}></span> Live Real-Time (15s)
            </span>
          </div>
          <p style={styles.subtitle}>
            Diperbarui otomatis secara real-time dari seluruh wallet Binance (Futures + Funding + Spot)
          </p>
        </div>

        {/* Timeframe Filters */}
        <div style={styles.filterBar}>
          {[
            { id: "7d", label: "7D" },
            { id: "30d", label: "30D" },
            { id: "90d", label: "90D" },
            { id: "1y", label: "1Y" },
            { id: "all", label: "ALL" },
          ].map((tf) => (
            <button
              key={tf.id}
              onClick={() => setRange(tf.id)}
              style={{
                ...styles.filterTab,
                ...(range === tf.id ? styles.filterTabActive : {}),
              }}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* Hero PnL Stat Banner */}
      <div style={styles.heroBanner}>
        <div style={styles.heroMain}>
          <span style={styles.heroLabel}>Kumulatif PnL ({range.toUpperCase()})</span>
          <div style={{ ...styles.heroValue, color: mainColor }}>
            {summary.real_trading_profit >= 0 ? `+$${summary.real_trading_profit.toFixed(2)}` : `-$${Math.abs(summary.real_trading_profit).toFixed(2)}`}
            <span style={styles.heroPct}>
              ({summary.trading_return_pct >= 0 ? `+${summary.trading_return_pct.toFixed(2)}%` : `${summary.trading_return_pct.toFixed(2)}%`})
            </span>
          </div>
        </div>

        {/* Binance Mobile Metric Grid */}
        <div style={styles.metricGrid}>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>Total Asset / NAV</span>
            <span style={styles.metricValue}>${summary.current_balance.toFixed(2)}</span>
            <span style={styles.metricSub}>
              Funding: <b>${summary.funding_balance.toFixed(2)}</b> | Futures: <b>${summary.futures_balance.toFixed(2)}</b>
            </span>
          </div>

          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>Rata-Rata PnL Harian</span>
            <span style={{ ...styles.metricValue, color: summary.daily_avg_pnl >= 0 ? "#0ecb81" : "#f6465d" }}>
              {summary.daily_avg_pnl >= 0 ? `+$${summary.daily_avg_pnl.toFixed(2)}` : `-$${Math.abs(summary.daily_avg_pnl).toFixed(2)}`}
            </span>
            <span style={styles.metricSub}>
              Floating UnPnl: <b style={{ color: summary.unrealized_pnl >= 0 ? "#0ecb81" : "#f6465d" }}>
                {summary.unrealized_pnl >= 0 ? `+$${summary.unrealized_pnl}` : `-$${Math.abs(summary.unrealized_pnl)}`}
              </b>
            </span>
          </div>

          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>Win / Loss Days</span>
            <span style={styles.metricValue}>
              <b style={{ color: "#0ecb81" }}>{summary.win_days} W</b> / <b style={{ color: "#f6465d" }}>{summary.loss_days} L</b>
            </span>
            <span style={styles.metricSub}>
              Win Rate: <b>{((summary.win_days / ((summary.win_days + summary.loss_days) || 1)) * 100).toFixed(1)}%</b>
            </span>
          </div>

          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>Max Drawdown</span>
            <span style={{ ...styles.metricValue, color: "#f6465d" }}>
              -{summary.max_drawdown_pct.toFixed(2)}%
            </span>
            <span style={styles.metricSub}>
              Net Transfer: <b>${summary.net_transfers.toFixed(2)}</b>
            </span>
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div style={styles.chartBox}>
        <div style={styles.chartHeader}>
          <span style={styles.chartTitle}>Grafik Kurva Kumulatif PnL (%)</span>
          <span style={styles.updateTime}>Terakhir Diperbarui: {lastUpdated.toLocaleTimeString("id-ID")} WIB</span>
        </div>

        {loading ? (
          <div style={styles.loadingBox}>⏳ Memuat data PnL real-time...</div>
        ) : error ? (
          <div style={styles.errorBox}>⚠️ {error}</div>
        ) : points.length === 0 ? (
          <div style={styles.loadingBox}>Belum ada histori trade untuk periode ini.</div>
        ) : (
          renderSvgChart()
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "16px",
    padding: "24px",
    color: "#eaecef",
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
    marginBottom: "20px",
  },
  titleGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  titleRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  title: {
    fontSize: "20px",
    fontWeight: "700",
    color: "#ffffff",
    margin: 0,
  },
  subtitle: {
    fontSize: "12px",
    color: "#848e9c",
    margin: 0,
  },
  liveBadge: {
    backgroundColor: "rgba(14, 203, 129, 0.15)",
    color: "#0ecb81",
    border: "1px solid rgba(14, 203, 129, 0.3)",
    fontSize: "11px",
    fontWeight: "700",
    padding: "3px 10px",
    borderRadius: "20px",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
  },
  liveDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    backgroundColor: "#0ecb81",
    boxShadow: "0 0 8px #0ecb81",
  },
  filterBar: {
    display: "flex",
    gap: "4px",
    backgroundColor: "#0b0e11",
    padding: "4px",
    borderRadius: "8px",
    border: "1px solid #2b313a",
  },
  filterTab: {
    backgroundColor: "transparent",
    border: "none",
    color: "#848e9c",
    padding: "6px 14px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  filterTabActive: {
    backgroundColor: "#2b313a",
    color: "#f0b90b", // Binance Gold
  },
  heroBanner: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    borderRadius: "12px",
    padding: "20px",
    marginBottom: "20px",
  },
  heroMain: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    marginBottom: "16px",
  },
  heroLabel: {
    fontSize: "12px",
    color: "#848e9c",
    fontWeight: "600",
  },
  heroValue: {
    fontSize: "32px",
    fontWeight: "800",
    display: "flex",
    alignItems: "baseline",
    gap: "10px",
  },
  heroPct: {
    fontSize: "18px",
    fontWeight: "700",
  },
  metricGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  metricCard: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "8px",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  metricLabel: {
    fontSize: "11px",
    color: "#848e9c",
    fontWeight: "600",
  },
  metricValue: {
    fontSize: "16px",
    fontWeight: "700",
    color: "#ffffff",
  },
  metricSub: {
    fontSize: "11px",
    color: "#848e9c",
  },
  chartBox: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    borderRadius: "12px",
    padding: "20px",
  },
  chartHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  chartTitle: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#eaecef",
  },
  updateTime: {
    fontSize: "11px",
    color: "#848e9c",
  },
  svg: {
    width: "100%",
    height: "300px",
    cursor: "crosshair",
  },
  tooltip: {
    position: "absolute",
    backgroundColor: "#1e2329",
    border: "1px solid #474d57",
    borderRadius: "8px",
    padding: "10px 14px",
    boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
    zIndex: 100,
    pointerEvents: "none",
    minWidth: "220px",
  },
  tooltipHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "11px",
    color: "#eaecef",
    borderBottom: "1px solid #2b313a",
    paddingBottom: "6px",
    marginBottom: "6px",
  },
  tooltipRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#848e9c",
    marginTop: "4px",
  },
  loadingBox: {
    textAlign: "center",
    color: "#848e9c",
    padding: "40px",
    fontSize: "14px",
  },
  errorBox: {
    textAlign: "center",
    color: "#f6465d",
    padding: "40px",
    fontSize: "14px",
  },
};

export default EquityCurveChart;
