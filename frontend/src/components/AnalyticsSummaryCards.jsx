import React from "react";

const AnalyticsSummaryCards = ({
  summary = {},
  filterSource,
  onFilterSourceChange,
  filterPair = "all",
  onFilterPairChange,
  filterSession = "all",
  onFilterSessionChange,
}) => {
  const coverage = summary.market_coverage || {
    bull: 0,
    bear: 0,
    range: 0,
    high_volatility: 0,
  };

  const netPnl = summary.total_net_pnl !== undefined ? Number(summary.total_net_pnl) : 0.0;
  const totalFee = summary.total_fee !== undefined ? Number(summary.total_fee) : 0.0;

  return (
    <div style={styles.wrapper}>
      {/* Header Controls & Filter Bar */}
      <div style={styles.toggleBar}>
        <div style={styles.leftFilterGroup}>
          <div style={styles.toggleGroup}>
            <button
              onClick={() => onFilterSourceChange("live")}
              style={{
                ...styles.toggleBtn,
                ...(filterSource === "live" ? styles.toggleBtnActive : {}),
              }}
            >
              🏷️ Trade Bertag Saja (Live)
            </button>
            <button
              onClick={() => onFilterSourceChange("all")}
              style={{
                ...styles.toggleBtn,
                ...(filterSource === "all" ? styles.toggleBtnActive : {}),
              }}
            >
              🌐 Semua Trade (+Import)
            </button>
          </div>

          {/* Pair Filter Dropdown */}
          <select
            value={filterPair}
            onChange={(e) => onFilterPairChange && onFilterPairChange(e.target.value)}
            style={styles.selectInput}
          >
            <option value="all">Semua Pair</option>
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
            <option value="SPKUSDT">SPKUSDT</option>
            <option value="CHILLGUYUSDT">CHILLGUYUSDT</option>
            <option value="VVVUSDT">VVVUSDT</option>
          </select>

          {/* Session Filter Dropdown */}
          <select
            value={filterSession}
            onChange={(e) => onFilterSessionChange && onFilterSessionChange(e.target.value)}
            style={styles.selectInput}
          >
            <option value="all">Semua Sesi</option>
            <option value="Asia">Sesi Asia</option>
            <option value="London">Sesi London</option>
            <option value="New York">Sesi New York</option>
          </select>
        </div>

        <span style={styles.toggleNote}>
          *Filter dinamis per sumber data, pair & sesi trading
        </span>
      </div>

      {/* Standalone Headline Metric Cards (12 Kartu Metrik Lengkap Dokumen Teknis Bab 5.5 & 13.4) */}
      <div style={styles.grid}>
        {/* Card 1: Expectancy */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>EXPECTANCY (EV)</span>
          <div style={{ ...styles.cardValue, color: (summary.expectancy_r || 0) >= 0 ? "#0ecb81" : "#f6465d" }}>
            {(summary.expectancy_r || 0) >= 0 ? `+${summary.expectancy_r}` : `${summary.expectancy_r}`} R
          </div>
          <span style={styles.cardSub}>Ekspektasi nilai hasil per trade</span>
        </div>

        {/* Card 2: Win Rate */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>WIN RATE</span>
          <div style={{ ...styles.cardValue, color: "#ffffff" }}>
            {summary.win_rate_pct || 0}%
          </div>
          <span style={styles.cardSub}>
            <b style={{ color: "#0ecb81" }}>{summary.winning_trades || 0} Win</b> / <b style={{ color: "#f6465d" }}>{summary.losing_trades || 0} Loss</b> ({summary.breakeven_trades || 0} BE)
          </span>
        </div>

        {/* Card 3: Average Realized RR */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>AVERAGE REALIZED RR</span>
          <div style={{ ...styles.cardValue, color: (summary.avg_realized_r || 0) >= 0 ? "#0ecb81" : "#f6465d" }}>
            {(summary.avg_realized_r || 0) >= 0 ? `+${summary.avg_realized_r}` : `${summary.avg_realized_r}`} R
          </div>
          <span style={styles.cardSub}>
            Avg Win: <b>+{(summary.avg_win_r || 0)}R</b> | Loss: <b>{(summary.avg_loss_r || 0)}R</b>
          </span>
        </div>

        {/* Card 4: Profit Factor */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>PROFIT FACTOR</span>
          <div style={{ ...styles.cardValue, color: (summary.profit_factor || 0) >= 1.0 ? "#0ecb81" : "#f6465d" }}>
            {summary.profit_factor || 0}
          </div>
          <span style={styles.cardSub}>Rasio Gross Profit vs Gross Loss</span>
        </div>

        {/* Card 5: Total Net PnL */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>TOTAL NET PnL ($)</span>
          <div style={{ ...styles.cardValue, color: netPnl >= 0 ? "#0ecb81" : "#f6465d" }}>
            {netPnl >= 0 ? `+$${netPnl.toFixed(2)}` : `-$${Math.abs(netPnl).toFixed(2)}`}
          </div>
          <span style={styles.cardSub}>Akumulasi keuntungan/kerugian bersih</span>
        </div>

        {/* Card 6: Total Fee */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>TOTAL BIAYA & KOMISI ($)</span>
          <div style={{ ...styles.cardValue, color: "#f0b90b" }}>
            -${totalFee.toFixed(2)}
          </div>
          <span style={styles.cardSub}>Biaya transaksi & funding fee exchange</span>
        </div>

        {/* Card 7: Max Drawdown */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>MAX DRAWDOWN (MAX DD)</span>
          <div style={{ ...styles.cardValue, color: "#f6465d" }}>
            -{(summary.max_drawdown_pct || 0).toFixed(2)}%
          </div>
          <span style={styles.cardSub}>
            Max Decline: <b>-${summary.max_drawdown_dollars || 0}</b>
          </span>
        </div>

        {/* Card 8: Recovery Factor */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>RECOVERY FACTOR</span>
          <div style={{ ...styles.cardValue, color: (summary.recovery_factor || 0) >= 1.0 ? "#0ecb81" : "#f0b90b" }}>
            {summary.recovery_factor || 0}
          </div>
          <span style={styles.cardSub}>Rasio Total Net PnL vs Max DD</span>
        </div>

        {/* Card 9: Avg Holding Time */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>AVG HOLDING TIME</span>
          <div style={{ ...styles.cardValue, color: "#a78bfa" }}>
            {summary.avg_holding_time_str || "0m"}
          </div>
          <span style={styles.cardSub}>Rata-rata durasi posisi terbuka</span>
        </div>

        {/* Card 10: Avg Return on Margin */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>AVG RETURN ON MARGIN</span>
          <div style={{ ...styles.cardValue, color: (summary.return_on_margin_pct || 0) >= 0 ? "#0ecb81" : "#f6465d" }}>
            {(summary.return_on_margin_pct || 0) >= 0 ? `+${summary.return_on_margin_pct}%` : `${summary.return_on_margin_pct}%`}
          </div>
          <span style={styles.cardSub}>
            Dampak Equity: <b>{(summary.equity_impact_pct || 0) >= 0 ? `+${summary.equity_impact_pct}%` : `${summary.equity_impact_pct}%`}</b>
          </span>
        </div>

        {/* Card 11: MFE / MAE */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>AVG MFE / MAE EXCURSION</span>
          <div style={{ ...styles.cardValue, color: "#a78bfa" }}>
            +{(summary.mfe_avg_r || 0)}R
          </div>
          <span style={styles.cardSub}>
            Max Adverse (MAE): <b style={{ color: "#f6465d" }}>{(summary.mae_avg_r || 0)}R</b>
          </span>
        </div>

        {/* Card 12: Total Populasi Trades */}
        <div style={styles.card}>
          <span style={styles.cardLabel}>VOLUMETRIK POPULASI ($n$)</span>
          <div style={{ ...styles.cardValue, color: "#38bdf8" }}>
            {summary.total_trades || 0} Trade
          </div>
          <span style={styles.cardSub}>
            <b style={{ color: "#0ecb81" }}>{summary.closed_trades || 0} Selesai</b> / <b style={{ color: "#fbbf24" }}>{(summary.total_trades || 0) - (summary.closed_trades || 0)} Aktif</b>
          </span>
        </div>
      </div>

      {/* Coverage Per Kondisi Market */}
      <div style={styles.coverageCard}>
        <div style={styles.coverageHeader}>
          <span style={styles.coverageTitle}>📊 COVERAGE PER KONDISI MARKET (JUMLAH TRADE)</span>
          <span style={styles.coverageSub}>Total {summary.closed_trades || 0} Closed Trades</span>
        </div>
        <div style={styles.pillsGrid}>
          <div style={styles.pillItem}>
            <span style={styles.pillLabel}>🐂 Bull Trend</span>
            <span style={{ ...styles.pillCount, color: "#0ecb81" }}>{coverage.bull}</span>
          </div>
          <div style={styles.pillItem}>
            <span style={styles.pillLabel}>🐻 Bear Trend</span>
            <span style={{ ...styles.pillCount, color: "#f6465d" }}>{coverage.bear}</span>
          </div>
          <div style={styles.pillItem}>
            <span style={styles.pillLabel}>↔️ Range Bound</span>
            <span style={{ ...styles.pillCount, color: "#f0b90b" }}>{coverage.range}</span>
          </div>
          <div style={styles.pillItem}>
            <span style={styles.pillLabel}>⚡ Volatilitas Tinggi</span>
            <span style={{ ...styles.pillCount, color: "#a78bfa" }}>{coverage.high_volatility}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const styles = {
  wrapper: {
    marginBottom: "28px",
  },
  toggleBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "12px",
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "14px",
    padding: "12px 20px",
    marginBottom: "20px",
  },
  leftFilterGroup: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "12px",
  },
  toggleGroup: {
    display: "flex",
    gap: "8px",
  },
  selectInput: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    color: "#eaecef",
    padding: "8px 12px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "600",
    outline: "none",
    cursor: "pointer",
  },
  toggleBtn: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    color: "#848e9c",
    padding: "8px 18px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  toggleBtnActive: {
    backgroundColor: "#2b313a",
    color: "#f0b90b",
    borderColor: "#f0b90b",
  },
  toggleNote: {
    fontSize: "12px",
    color: "#848e9c",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
    marginBottom: "20px",
  },
  card: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "14px",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    boxSizing: "border-box",
    minWidth: "0",
  },
  cardLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#848e9c",
    letterSpacing: "0.5px",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  cardValue: {
    fontSize: "26px",
    fontWeight: "800",
    lineHeight: "1.2",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  cardSub: {
    fontSize: "12px",
    color: "#94a3b8",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  coverageCard: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "14px",
    padding: "18px 20px",
  },
  coverageHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "14px",
  },
  coverageTitle: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#848e9c",
    letterSpacing: "0.5px",
  },
  coverageSub: {
    fontSize: "12px",
    color: "#cbd5e1",
  },
  pillsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: "12px",
  },
  pillItem: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    borderRadius: "10px",
    padding: "10px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  pillLabel: {
    fontSize: "12px",
    fontWeight: "600",
    color: "#eaecef",
  },
  pillCount: {
    fontSize: "16px",
    fontWeight: "800",
  },
};

export default AnalyticsSummaryCards;
