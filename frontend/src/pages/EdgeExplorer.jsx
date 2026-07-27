import React, { useState, useEffect } from "react";

const EdgeExplorer = () => {
  const [blueprints, setBlueprints] = useState([]);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [edgeDetail, setEdgeDetail] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryMessage, setDiscoveryMessage] = useState(null);

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchBlueprints = async (statusVal = "all") => {
    setLoading(true);
    try {
      const url = statusVal === "all"
        ? "http://localhost:8000/api/v1/edges/blueprints"
        : `http://localhost:8000/api/v1/edges/blueprints?status=${statusVal}`;
      
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setBlueprints(data);
      }
    } catch (err) {
      console.error("Gagal mengambil data Edge Blueprints:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEdgeDetail = async (edgeId) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/edges/blueprints/${edgeId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEdgeDetail(data);
      }
    } catch (err) {
      console.error("Gagal mengambil detail Edge Blueprint:", err);
    }
  };

  const handleRunDiscovery = async () => {
    setDiscovering(true);
    setDiscoveryMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/edges/discover", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const result = await res.json();
        if (result.status === "skipped") {
          setDiscoveryMessage({
            type: "warning",
            text: `⚠️ Discovery Di-Jeda: ${result.reason}`,
          });
        } else if (result.status === "completed") {
          setDiscoveryMessage({
            type: "success",
            text: `✅ Discovery Selesai: Mengevaluasi ${result.total_trades_analyzed} trade. ${result.edges_discovered} blueprint edge ditemukan/diperbarui!`,
          });
          await fetchBlueprints(statusFilter);
        }
      }
    } catch (err) {
      setDiscoveryMessage({
        type: "error",
        text: "❌ Gagal menjalankan Edge Discovery Engine.",
      });
    } finally {
      setDiscovering(false);
    }
  };

  useEffect(() => {
    fetchBlueprints(statusFilter);
  }, [statusFilter]);

  const getStatusBadge = (st) => {
    switch (st) {
      case "production":
        return { label: "PRODUCTION", bg: "rgba(14, 203, 129, 0.15)", color: "#0ecb81", border: "1px solid #0ecb81" };
      case "validation":
        return { label: "VALIDATION", bg: "rgba(59, 130, 246, 0.15)", color: "#3b82f6", border: "1px solid #3b82f6" };
      case "research":
        return { label: "RESEARCH", bg: "rgba(240, 185, 11, 0.15)", color: "#f0b90b", border: "1px solid #f0b90b" };
      case "learning":
        return { label: "LEARNING", bg: "rgba(167, 139, 250, 0.15)", color: "#a78bfa", border: "1px solid #a78bfa" };
      case "monitoring":
        return { label: "MONITORING", bg: "rgba(246, 70, 93, 0.15)", color: "#f6465d", border: "1px solid #f6465d" };
      default:
        return { label: st.toUpperCase(), bg: "#2b313a", color: "#848e9c", border: "1px solid #474d57" };
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.headerRow}>
          <div>
            <div style={styles.badgePill}>
              <span style={styles.badgeDot}></span> FITUR 12 — EDGE DISCOVERY ENGINE
            </div>
            <h1 style={styles.title}>Edge Blueprint Explorer</h1>
            <p style={styles.subtitle}>
              Penemu kombinasi setup statistik ilmiah dengan 10.000 iterasi Bootstrap Resampling & Koreksi FDR Benjamini-Hochberg.
            </p>
          </div>
          <button
            onClick={handleRunDiscovery}
            disabled={discovering}
            style={styles.btnDiscover}
          >
            {discovering ? "⏳ Mengkalkulasi 10k Resample..." : "⚡ Jalankan Engine Discovery"}
          </button>
        </div>

        {/* Discovery Status / Notification Banner */}
        {discoveryMessage && (
          <div
            style={{
              backgroundColor: discoveryMessage.type === "warning" ? "rgba(240, 185, 11, 0.15)" : discoveryMessage.type === "success" ? "rgba(14, 203, 129, 0.15)" : "rgba(246, 70, 93, 0.15)",
              border: discoveryMessage.type === "warning" ? "1px solid #f0b90b" : discoveryMessage.type === "success" ? "1px solid #0ecb81" : "1px solid #f6465d",
              color: discoveryMessage.type === "warning" ? "#f0b90b" : discoveryMessage.type === "success" ? "#0ecb81" : "#f6465d",
              padding: "14px 20px",
              borderRadius: "12px",
              fontSize: "13px",
              fontWeight: "600",
              marginBottom: "20px",
            }}
          >
            {discoveryMessage.text}
          </div>
        )}

        {/* Status Filter Tabs */}
        <div style={styles.filterTabs}>
          {["all", "production", "validation", "research", "learning", "monitoring"].map((tab) => (
            <button
              key={tab}
              onClick={() => setStatusFilter(tab)}
              style={{
                ...styles.tabBtn,
                ...(statusFilter === tab ? styles.tabBtnActive : {}),
              }}
            >
              {tab === "all" ? "Semua Status" : tab.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Blueprints Table / Cards */}
        {loading ? (
          <div style={styles.loadingBox}>⏳ Memuat data Edge Blueprints...</div>
        ) : blueprints.length === 0 ? (
          <div style={styles.emptyBox}>
            <p style={{ margin: 0, fontWeight: "600" }}>Belum ada Edge Blueprint yang ditemukan.</p>
            <span style={{ fontSize: "12px", color: "#848e9c" }}>
              Klik tombol '⚡ Jalankan Engine Discovery' di atas untuk memproses data trade bertag Anda.
            </span>
          </div>
        ) : (
          <div style={styles.grid}>
            {blueprints.map((bp) => {
              const badge = getStatusBadge(bp.status);
              return (
                <div
                  key={bp.id}
                  style={styles.card}
                  onClick={() => {
                    setSelectedEdge(bp);
                    fetchEdgeDetail(bp.id);
                  }}
                >
                  <div style={styles.cardHeader}>
                    <span style={{ ...styles.statusBadge, backgroundColor: badge.bg, color: badge.color, border: badge.border }}>
                      {badge.label}
                    </span>
                    <span style={styles.sampleBadge}>n = {bp.sample_size} trade</span>
                  </div>

                  <h3 style={styles.edgeName}>{bp.name}</h3>

                  <div style={styles.tagsContainer}>
                    {(bp.setup_combination || []).map((tag, idx) => (
                      <span key={idx} style={styles.tagPill}>
                        🏷️ {tag}
                      </span>
                    ))}
                  </div>

                  <div style={styles.statsRow}>
                    <div style={styles.statBox}>
                      <span style={styles.statLabel}>EXPECTANCY (95% CI)</span>
                      <span style={{ ...styles.statVal, color: bp.expectancy_r >= 0 ? "#0ecb81" : "#f6465d" }}>
                        {bp.expectancy_r >= 0 ? `+${bp.expectancy_r}` : `${bp.expectancy_r}`} R
                      </span>
                      <span style={styles.ciSub}>
                        [{bp.ci_lower}R — {bp.ci_upper}R]
                      </span>
                    </div>

                    <div style={styles.statBox}>
                      <span style={styles.statLabel}>WIN RATE (WILSON 95%)</span>
                      <span style={styles.statVal}>{bp.win_rate_pct}%</span>
                      <span style={styles.ciSub}>
                        [{bp.win_rate_ci_lower}% — {bp.win_rate_ci_upper}%]
                      </span>
                    </div>
                  </div>

                  <div style={styles.cardFooter}>
                    <span style={styles.fdrBadge}>
                      {bp.is_fdr_significant ? "✅ Signifikan (FDR 5%)" : "⚠️ p-val = " + bp.p_value}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedEdge(bp);
                        fetchEdgeDetail(bp.id);
                      }}
                      style={styles.btnDetailText}
                    >
                      Lihat Detail →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Edge Detail Modal (Mockup 13.6) */}
        {selectedEdge && (
          <div style={styles.modalOverlay} onClick={() => { setSelectedEdge(null); setEdgeDetail(null); }}>
            <div style={styles.modalBox} onClick={(e) => e.stopPropagation()}>
              <div style={styles.modalHeader}>
                <div>
                  <span style={{ ...styles.statusBadge, ...getStatusBadge(selectedEdge.status) }}>
                    {getStatusBadge(selectedEdge.status).label}
                  </span>
                  <h2 style={styles.modalTitle}>{selectedEdge.name}</h2>
                </div>
                <button onClick={() => { setSelectedEdge(null); setEdgeDetail(null); }} style={styles.closeBtn}>✕</button>
              </div>

              {/* Checklist Validasi */}
              <div style={styles.checklistCard}>
                <h4 style={styles.checklistTitle}>📋 Kriteria Validasi Statistik Edge</h4>
                <div style={styles.checklistGrid}>
                  <div style={styles.checkItem}>
                    <span>{selectedEdge.is_fdr_significant ? "✅" : "❌"}</span>
                    <span>Signifikan Statistik (FDR 5% Passed)</span>
                  </div>
                  <div style={styles.checkItem}>
                    <span>{selectedEdge.sample_size >= 30 ? "✅" : "⚠️"}</span>
                    <span>Kecukupan Sampel (n = {selectedEdge.sample_size} trade)</span>
                  </div>
                  <div style={styles.checkItem}>
                    <span>{selectedEdge.ci_lower > 0 ? "✅" : "❌"}</span>
                    <span>Batas Bawah CI 95% Positif ({selectedEdge.ci_lower}R)</span>
                  </div>
                  <div style={styles.checkItem}>
                    <span>{selectedEdge.out_of_sample_expectancy_r > 0 ? "✅" : "⚠️"}</span>
                    <span>Out-of-Sample Validated ({selectedEdge.out_of_sample_expectancy_r}R)</span>
                  </div>
                </div>
              </div>

              {/* Contributing Trades Table */}
              <div style={styles.tradesSection}>
                <h4 style={styles.tradesTitle}>
                  📖 Daftar {edgeDetail && edgeDetail.contributing_trades ? edgeDetail.contributing_trades.length : 0} Trade Berkontribusi
                </h4>
                {!edgeDetail ? (
                  <div style={{ textAlign: "center", padding: "20px", color: "#848e9c" }}>⏳ Memuat rincian trade berkontribusi...</div>
                ) : (
                  <div style={styles.tableScroll}>
                    <table style={styles.table}>
                      <thead>
                        <tr>
                          <th style={styles.th}>Pair</th>
                          <th style={styles.th}>Direction</th>
                          <th style={styles.th}>Entry Time</th>
                          <th style={styles.th}>Realized RR</th>
                          <th style={styles.th}>PnL ($)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(edgeDetail.contributing_trades || []).map((t) => (
                          <tr key={t.id} style={styles.tr}>
                            <td style={styles.td}><b>{t.pair}</b></td>
                            <td style={styles.td}>
                              <span style={{ color: t.direction === "long" ? "#0ecb81" : "#f6465d", fontWeight: "700" }}>
                                {t.direction.toUpperCase()}
                              </span>
                            </td>
                            <td style={styles.td}>{t.entry_time ? t.entry_time.replace("T", " ").substring(0, 16) : "-"}</td>
                            <td style={{ ...styles.td, color: t.rr_realized >= 0 ? "#0ecb81" : "#f6465d", fontWeight: "700" }}>
                              {t.rr_realized >= 0 ? `+${t.rr_realized}` : t.rr_realized} R
                            </td>
                            <td style={{ ...styles.td, color: t.pnl >= 0 ? "#0ecb81" : "#f6465d" }}>
                              {t.pnl >= 0 ? `+$${t.pnl}` : `-$${Math.abs(t.pnl)}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
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
    padding: "24px",
  },
  content: {
    maxWidth: "1280px",
    margin: "0 auto",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px",
    marginBottom: "24px",
  },
  badgePill: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    backgroundColor: "rgba(139, 92, 246, 0.15)",
    border: "1px solid rgba(139, 92, 246, 0.3)",
    color: "#a78bfa",
    fontSize: "11px",
    fontWeight: "700",
    padding: "4px 12px",
    borderRadius: "20px",
    marginBottom: "6px",
  },
  badgeDot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    backgroundColor: "#a78bfa",
    boxShadow: "0 0 8px #a78bfa",
  },
  title: {
    fontSize: "24px",
    fontWeight: "800",
    color: "#ffffff",
    margin: 0,
  },
  subtitle: {
    fontSize: "14px",
    color: "#94a3b8",
    margin: "4px 0 0 0",
  },
  btnDiscover: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    padding: "12px 22px",
    borderRadius: "12px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 4px 16px rgba(124, 58, 237, 0.4)",
    transition: "all 0.2s",
  },
  filterTabs: {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
    marginBottom: "24px",
  },
  tabBtn: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    color: "#848e9c",
    padding: "8px 16px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  tabBtnActive: {
    backgroundColor: "#2b313a",
    color: "#f0b90b",
    borderColor: "#f0b90b",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "20px",
  },
  card: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "16px",
    padding: "20px",
    cursor: "pointer",
    transition: "transform 0.2s, border-color 0.2s",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusBadge: {
    fontSize: "10px",
    fontWeight: "800",
    padding: "3px 10px",
    borderRadius: "20px",
    letterSpacing: "0.5px",
  },
  sampleBadge: {
    fontSize: "11px",
    color: "#848e9c",
    fontWeight: "600",
  },
  edgeName: {
    fontSize: "16px",
    fontWeight: "700",
    color: "#ffffff",
    margin: 0,
  },
  tagsContainer: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
  },
  tagPill: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    color: "#cbd5e1",
    fontSize: "11px",
    fontWeight: "600",
    padding: "3px 8px",
    borderRadius: "6px",
  },
  statsRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "12px",
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    borderRadius: "12px",
    padding: "12px",
  },
  statBox: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  statLabel: {
    fontSize: "10px",
    fontWeight: "700",
    color: "#848e9c",
  },
  statVal: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#ffffff",
  },
  ciSub: {
    fontSize: "10px",
    color: "#94a3b8",
  },
  cardFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderTop: "1px solid #2b313a",
    paddingTop: "10px",
    marginTop: "4px",
  },
  fdrBadge: {
    fontSize: "11px",
    color: "#0ecb81",
    fontWeight: "600",
  },
  btnDetailText: {
    backgroundColor: "rgba(167, 139, 250, 0.12)",
    border: "1px solid rgba(167, 139, 250, 0.3)",
    fontSize: "12px",
    color: "#a78bfa",
    fontWeight: "700",
    padding: "6px 14px",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  loadingBox: {
    textAlign: "center",
    padding: "60px",
    color: "#848e9c",
  },
  emptyBox: {
    backgroundColor: "#181a20",
    border: "1px dashed #2b313a",
    borderRadius: "16px",
    padding: "60px",
    textAlign: "center",
    color: "#eaecef",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    backdropFilter: "blur(8px)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 2000,
    padding: "20px",
  },
  modalBox: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "20px",
    width: "100%",
    maxWidth: "800px",
    maxHeight: "90vh",
    overflowY: "auto",
    padding: "24px",
    boxShadow: "0 20px 50px rgba(0,0,0,0.8)",
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "20px",
  },
  modalTitle: {
    fontSize: "20px",
    fontWeight: "800",
    color: "#ffffff",
    margin: "6px 0 0 0",
  },
  closeBtn: {
    backgroundColor: "transparent",
    border: "none",
    color: "#848e9c",
    fontSize: "20px",
    cursor: "pointer",
  },
  checklistCard: {
    backgroundColor: "#0b0e11",
    border: "1px solid #2b313a",
    borderRadius: "14px",
    padding: "16px",
    marginBottom: "20px",
  },
  checklistTitle: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#ffffff",
    margin: "0 0 12px 0",
  },
  checklistGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "10px",
  },
  checkItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "12px",
    color: "#cbd5e1",
  },
  tradesSection: {
    marginTop: "16px",
  },
  tradesTitle: {
    fontSize: "14px",
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: "12px",
  },
  tableScroll: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    textAlign: "left",
    fontSize: "11px",
    fontWeight: "700",
    color: "#848e9c",
    padding: "10px",
    borderBottom: "1px solid #2b313a",
  },
  td: {
    fontSize: "12px",
    padding: "10px",
    borderBottom: "1px solid #2b313a",
  },
  tr: {
    transition: "background 0.2s",
  },
};

export default EdgeExplorer;
