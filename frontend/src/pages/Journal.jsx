import React, { useState, useEffect } from "react";
import MarketContextCard from "../components/MarketContextCard";

const Journal = () => {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all"); // 'all', 'binance_sync', 'historical_import'
  const [statusFilter, setStatusFilter] = useState("all"); // 'all', 'open', 'closed'
  const [selectedTrade, setSelectedTrade] = useState(null);

  const token = localStorage.getItem("token");

  const fetchJournalList = async () => {
    setLoading(true);
    setError("");
    try {
      let url = `http://localhost:8000/api/v1/journal/list?data_source=${sourceFilter}&status_filter=${statusFilter}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Gagal memuat daftar jurnal.`);
      }

      const data = await res.json();
      setTrades(data.trades || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJournalList();
  }, [sourceFilter, statusFilter]);

  // Helper metrics
  const totalTrades = trades.length;
  const closedTrades = trades.filter((t) => t.status === "Closed");
  const winTrades = closedTrades.filter((t) => (t.pnl || 0) > 0);
  const winRate = closedTrades.length > 0 ? ((winTrades.length / closedTrades.length) * 100).toFixed(1) : "0.0";
  const totalNetPnl = closedTrades.reduce((acc, t) => acc + (t.pnl || 0), 0);
  const avgRR = closedTrades.length > 0
    ? (closedTrades.reduce((acc, t) => acc + (t.rr_realized || 0), 0) / closedTrades.length).toFixed(2)
    : "0.00";

  const formatHoldingTime = (sec) => {
    if (sec === null || sec === undefined) return "—";
    if (sec < 60) return `${sec}d`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}d`;
    const hours = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    return `${hours}j ${mins}m`;
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.header}>
          <div>
            <h1 style={styles.title}>Daftar Jurnal Trading (Trade Journal List)</h1>
            <p style={styles.subtitle}>
              Koleksi lengkap seluruh eksekusi trade manual dan sinkronisasi Binance dengan metrik VWAP, Realized PnL, dan RR.
            </p>
          </div>
        </div>

        {/* Summary Metric Cards */}
        <div style={styles.summaryGrid}>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>TOTAL TRADE</span>
            <span style={styles.summaryValue}>{totalTrades}</span>
          </div>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>TOTAL NET PnL</span>
            <span style={{
              ...styles.summaryValue,
              color: totalNetPnl >= 0 ? "#22c55e" : "#ef4444"
            }}>
              {totalNetPnl >= 0 ? `+$${totalNetPnl.toFixed(2)}` : `-$${Math.abs(totalNetPnl).toFixed(2)}`}
            </span>
          </div>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>WIN RATE</span>
            <span style={{ ...styles.summaryValue, color: parseFloat(winRate) >= 50 ? "#22c55e" : "#f59e0b" }}>
              {winRate}%
            </span>
          </div>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}>AVG REALIZED RR</span>
            <span style={styles.summaryValue}>
              {avgRR}R
            </span>
          </div>
        </div>

        {/* Filters */}
        <div style={styles.filterBar}>
          <div style={styles.tabGroup}>
            <button
              onClick={() => setSourceFilter("all")}
              style={sourceFilter === "all" ? styles.tabActive : styles.tab}
            >
              Semua Sumber
            </button>
            <button
              onClick={() => setSourceFilter("binance_sync")}
              style={sourceFilter === "binance_sync" ? styles.tabActive : styles.tab}
            >
              🟢 Live (Binance)
            </button>
            <button
              onClick={() => setSourceFilter("historical_import")}
              style={sourceFilter === "historical_import" ? styles.tabActive : styles.tab}
            >
              🟣 Import
            </button>
          </div>

          <div style={styles.selectGroup}>
            <label style={styles.selectLabel}>Status:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={styles.select}
            >
              <option value="all">Semua Status</option>
              <option value="open">Aktif (Open)</option>
              <option value="closed">Selesai (Closed)</option>
            </select>
          </div>
        </div>

        {/* Error message */}
        {error && <div style={styles.errorBanner}>{error}</div>}

        {/* Loading state */}
        {loading ? (
          <div style={styles.loadingContainer}>
            <div style={styles.spinner} />
            <p style={styles.loadingText}>Memuat daftar jurnal trade...</p>
          </div>
        ) : trades.length === 0 ? (
          <div style={styles.emptyContainer}>
            <p style={styles.emptyText}>Tidak ada data trade yang sesuai dengan filter.</p>
          </div>
        ) : (
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>SUMBER</th>
                  <th style={styles.th}>PAIR</th>
                  <th style={styles.th}>DIR</th>
                  <th style={styles.th}>ENTRY (VWAP)</th>
                  <th style={styles.th}>EXIT (VWAP)</th>
                  <th style={styles.th}>NET PnL</th>
                  <th style={styles.th}>REALIZED RR</th>
                  <th style={styles.th}>FEE</th>
                  <th style={styles.th}>HOLDING TIME</th>
                  <th style={styles.th}>SETUP</th>
                  <th style={styles.th}>STATUS</th>
                  <th style={styles.th}>DETAIL</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <React.Fragment key={t.id}>
                    <tr style={styles.tr}>
                      <td style={styles.td}>
                        <span style={t.source_badge === "Live" ? styles.badgeLive : styles.badgeImport}>
                          {t.source_badge}
                        </span>
                      </td>
                      <td style={styles.tdBold}>{t.pair}</td>
                      <td style={styles.td}>
                        <span style={t.direction === "long" ? styles.badgeLong : styles.badgeShort}>
                          {t.direction.toUpperCase()}
                        </span>
                      </td>
                      <td style={styles.tdNum}>${t.entry_price.toFixed(4)}</td>
                      <td style={styles.tdNum}>
                        {t.exit_price ? `$${t.exit_price.toFixed(4)}` : "—"}
                      </td>
                      <td style={{
                        ...styles.tdNum,
                        fontWeight: "700",
                        color: t.pnl === null ? "#94a3b8" : t.pnl >= 0 ? "#22c55e" : "#ef4444"
                      }}>
                        {t.pnl === null ? "—" : t.pnl >= 0 ? `+$${t.pnl.toFixed(2)}` : `-$${Math.abs(t.pnl).toFixed(2)}`}
                      </td>
                      <td style={styles.tdNum}>
                        {t.rr_realized !== null ? `${t.rr_realized.toFixed(2)}R` : "—"}
                      </td>
                      <td style={styles.tdNum}>
                        {t.fee !== null ? `$${t.fee.toFixed(4)}` : "—"}
                      </td>
                      <td style={styles.td}>{formatHoldingTime(t.holding_time_sec)}</td>
                      <td style={styles.td}>
                        {t.setups && t.setups.length > 0 ? (
                          <div style={styles.setupTags}>
                            {t.setups.map((s, idx) => (
                              <span key={idx} style={styles.setupPill}>{s}</span>
                            ))}
                          </div>
                        ) : (
                          <span style={styles.dimText}>—</span>
                        )}
                      </td>
                      <td style={styles.td}>
                        <span style={t.status === "Closed" ? styles.badgeClosed : styles.badgeOpen}>
                          {t.status}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <button
                          onClick={() => setSelectedTrade(selectedTrade?.id === t.id ? null : t)}
                          style={styles.detailBtn}
                        >
                          {selectedTrade?.id === t.id ? "Tutup ▲" : "Rincian ▼"}
                        </button>
                      </td>
                    </tr>

                    {/* Expanded Detail Panel */}
                    {selectedTrade?.id === t.id && (
                      <tr>
                        <td colSpan={12} style={styles.detailTd}>
                          <div style={styles.expandedPanel}>
                            <h4 style={styles.panelTitle}>Rincian Eksekusi & Context: {t.pair}</h4>
                            
                            {/* Fills Table */}
                            <div style={styles.fillsSection}>
                              <h5 style={styles.subTitle}>Fill Binance Terhubung ({t.fills ? t.fills.length : 0})</h5>
                              {t.fills && t.fills.length > 0 ? (
                                <table style={styles.miniTable}>
                                  <thead>
                                    <tr>
                                      <th style={styles.miniTh}>Role</th>
                                      <th style={styles.miniTh}>Binance Trade ID</th>
                                      <th style={styles.miniTh}>Side</th>
                                      <th style={styles.miniTh}>Harga</th>
                                      <th style={styles.miniTh}>Kuantitas</th>
                                      <th style={styles.miniTh}>Fee</th>
                                      <th style={styles.miniTh}>Waktu Eksekusi</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {t.fills.map((f) => (
                                      <tr key={f.id} style={styles.miniTr}>
                                        <td style={styles.miniTd}>
                                          <span style={f.role === "entry" ? styles.badgeEntry : styles.badgeExit}>
                                            {f.role.toUpperCase()}
                                          </span>
                                        </td>
                                        <td style={styles.miniTd}>{f.binance_trade_id}</td>
                                        <td style={styles.miniTd}>{f.side}</td>
                                        <td style={styles.miniTd}>${f.price.toFixed(4)}</td>
                                        <td style={styles.miniTd}>{f.qty}</td>
                                        <td style={styles.miniTd}>${f.fee.toFixed(4)}</td>
                                        <td style={styles.miniTd}>
                                          {f.executed_at ? new Date(f.executed_at).toLocaleString("id-ID") : "—"}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              ) : (
                                <p style={styles.dimText}>Belum ada fill terhubung.</p>
                              )}
                            </div>

                            {/* Screenshot & Context */}
                            <div style={styles.contextGrid}>
                              {t.screenshot_url && (
                                <div style={styles.screenshotBox}>
                                  <h5 style={styles.subTitle}>Screenshot Sebelum Entry</h5>
                                  <img src={t.screenshot_url} alt="Chart Screenshot" style={styles.screenshotImg} />
                                </div>
                              )}

                              {t.market_context && (
                                <div style={{ flex: 1 }}>
                                  <MarketContextCard contextData={t.market_context} />
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    minHeight: "calc(100vh - 70px)",
    backgroundColor: "#0d0a1b",
    color: "#e2e8f0",
    fontFamily: "'Inter', sans-serif",
    padding: "40px 20px",
  },
  content: {
    maxWidth: "1300px",
    margin: "0 auto",
  },
  header: {
    marginBottom: "25px",
  },
  title: {
    fontSize: "28px",
    fontWeight: "800",
    color: "#ffffff",
    margin: "0 0 8px 0",
  },
  subtitle: {
    fontSize: "14px",
    color: "#94a3b8",
    margin: 0,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
    marginBottom: "30px",
  },
  summaryCard: {
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    backdropFilter: "blur(16px)",
    border: "1px solid rgba(99, 102, 241, 0.25)",
    borderRadius: "14px",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  summaryLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: "1px",
  },
  summaryValue: {
    fontSize: "24px",
    fontWeight: "800",
    color: "#ffffff",
  },
  filterBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "20px",
    flexWrap: "wrap",
    gap: "16px",
  },
  tabGroup: {
    display: "flex",
    gap: "8px",
    background: "rgba(255, 255, 255, 0.03)",
    padding: "4px",
    borderRadius: "10px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
  },
  tab: {
    padding: "8px 16px",
    borderRadius: "8px",
    border: "none",
    background: "transparent",
    color: "#94a3b8",
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  tabActive: {
    padding: "8px 16px",
    borderRadius: "8px",
    border: "none",
    background: "#7c3aed",
    color: "#ffffff",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 0 12px rgba(124, 58, 237, 0.4)",
  },
  selectGroup: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  selectLabel: {
    fontSize: "13px",
    color: "#94a3b8",
  },
  select: {
    padding: "8px 14px",
    borderRadius: "8px",
    background: "#1e1b4b",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    color: "#ffffff",
    fontSize: "13px",
    outline: "none",
  },
  tableWrapper: {
    overflowX: "auto",
    background: "rgba(15, 23, 42, 0.75)",
    borderRadius: "14px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    textAlign: "left",
  },
  th: {
    padding: "14px 16px",
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
    letterSpacing: "0.5px",
  },
  tr: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
    transition: "background 0.2s ease",
  },
  td: {
    padding: "14px 16px",
    fontSize: "13px",
    color: "#e2e8f0",
  },
  tdBold: {
    padding: "14px 16px",
    fontSize: "13px",
    fontWeight: "700",
    color: "#ffffff",
  },
  tdNum: {
    padding: "14px 16px",
    fontSize: "13px",
    fontVariantNumeric: "tabular-nums",
  },
  badgeLive: {
    background: "rgba(34, 197, 94, 0.15)",
    color: "#22c55e",
    border: "1px solid rgba(34, 197, 94, 0.3)",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
  },
  badgeImport: {
    background: "rgba(168, 85, 247, 0.15)",
    color: "#a855f7",
    border: "1px solid rgba(168, 85, 247, 0.3)",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
  },
  badgeLong: {
    color: "#22c55e",
    fontWeight: "700",
  },
  badgeShort: {
    color: "#ef4444",
    fontWeight: "700",
  },
  badgeOpen: {
    background: "rgba(59, 130, 246, 0.15)",
    color: "#60a5fa",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "600",
  },
  badgeClosed: {
    background: "rgba(148, 163, 184, 0.15)",
    color: "#94a3b8",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "600",
  },
  setupTags: {
    display: "flex",
    gap: "4px",
    flexWrap: "wrap",
  },
  setupPill: {
    background: "rgba(124, 58, 237, 0.2)",
    color: "#c084fc",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "600",
  },
  dimText: {
    color: "#64748b",
    fontSize: "12px",
  },
  detailBtn: {
    background: "rgba(255, 255, 255, 0.05)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    color: "#c7d2fe",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "11px",
    cursor: "pointer",
  },
  detailTd: {
    padding: "16px 24px",
    background: "rgba(15, 23, 42, 0.95)",
    borderBottom: "1px solid rgba(124, 58, 237, 0.3)",
  },
  expandedPanel: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  panelTitle: {
    margin: 0,
    fontSize: "15px",
    fontWeight: "700",
    color: "#c7d2fe",
  },
  subTitle: {
    margin: "0 0 8px 0",
    fontSize: "12px",
    fontWeight: "700",
    color: "#94a3b8",
    letterSpacing: "0.5px",
  },
  fillsSection: {
    background: "rgba(0, 0, 0, 0.2)",
    padding: "14px",
    borderRadius: "10px",
  },
  miniTable: {
    width: "100%",
    borderCollapse: "collapse",
  },
  miniTh: {
    padding: "8px",
    fontSize: "10px",
    color: "#64748b",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  },
  miniTr: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.03)",
  },
  miniTd: {
    padding: "8px",
    fontSize: "11px",
    color: "#cbd5e1",
  },
  badgeEntry: {
    color: "#22c55e",
    fontWeight: "700",
  },
  badgeExit: {
    color: "#ef4444",
    fontWeight: "700",
  },
  contextGrid: {
    display: "flex",
    gap: "20px",
    flexWrap: "wrap",
  },
  screenshotBox: {
    width: "320px",
  },
  screenshotImg: {
    width: "100%",
    borderRadius: "8px",
    border: "1px solid rgba(255, 255, 255, 0.15)",
  },
  loadingContainer: {
    textAlign: "center",
    padding: "60px 0",
  },
  spinner: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    border: "3px solid rgba(124, 58, 237, 0.2)",
    borderTop: "3px solid #7c3aed",
    animation: "spin 0.8s linear infinite",
    margin: "0 auto 16px auto",
  },
  loadingText: {
    color: "#64748b",
    fontSize: "14px",
  },
  emptyContainer: {
    textAlign: "center",
    padding: "60px 0",
    background: "rgba(15, 23, 42, 0.5)",
    borderRadius: "14px",
    border: "1px dashed rgba(255, 255, 255, 0.1)",
  },
  emptyText: {
    color: "#64748b",
    fontSize: "14px",
  },
  errorBanner: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    color: "#ef4444",
    padding: "12px 16px",
    borderRadius: "8px",
    marginBottom: "20px",
    fontSize: "13px",
  },
};

export default Journal;
