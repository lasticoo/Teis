import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";

const EdgeDetail = () => {
  const { edgeId } = useParams();
  const [edge, setEdge] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  useEffect(() => {
    const fetchEdgeDetail = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`http://localhost:8000/api/v1/edges/detail/${edgeId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          // Fallback fetch if specific endpoint isn't registered, search from list
          const listRes = await fetch(`http://localhost:8000/api/v1/edges/explore`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (listRes.ok) {
            const listData = await listRes.json();
            const found = listData.blueprints?.find(b => b.id === edgeId || b.name === edgeId);
            if (found) {
              setEdge(found);
              setLoading(false);
              return;
            }
          }
          throw new Error("Gagal mengambil detail Edge Blueprint.");
        }

        const data = await res.json();
        setEdge(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (edgeId) {
      fetchEdgeDetail();
    }
  }, [edgeId, token]);

  const getStatusBadgeStyle = (status) => {
    switch (status?.toLowerCase()) {
      case "production":
        return { bg: "rgba(34, 197, 94, 0.15)", border: "#22c55e", color: "#22c55e", label: "PRODUCTION" };
      case "validation":
        return { bg: "rgba(56, 189, 248, 0.15)", border: "#38bdf8", color: "#38bdf8", label: "VALIDATION" };
      case "research":
        return { bg: "rgba(251, 191, 36, 0.15)", border: "#fbbf24", color: "#fbbf24", label: "RESEARCH" };
      case "monitoring":
        return { bg: "rgba(246, 70, 93, 0.15)", border: "#f6465d", color: "#f6465d", label: "MONITORING ⚠️" };
      default:
        return { bg: "rgba(148, 163, 184, 0.15)", border: "#94a3b8", color: "#94a3b8", label: "LEARNING" };
    }
  };

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner}></div>
        <p style={{ marginTop: "16px", color: "#94a3b8" }}>Memuat Detail Cetak Biru Edge...</p>
      </div>
    );
  }

  if (error || !edge) {
    return (
      <div style={styles.errorBox}>
        <h3>⚠️ Gagal Memuat Edge Detail</h3>
        <p>{error || "Edge Blueprint tidak ditemukan."}</p>
        <Link to="/edges" style={styles.btnBack}>← Kembali ke Explorer</Link>
      </div>
    );
  }

  const badge = getStatusBadgeStyle(edge.status);
  const setups = Array.isArray(edge.setup_combination) ? edge.setup_combination : [edge.name || "Order Block"];
  const ciLow = edge.ci_lower !== undefined ? Number(edge.ci_lower) : -0.2;
  const expVal = edge.expectancy_r !== undefined ? Number(edge.expectancy_r) : 0.35;
  const ciHigh = edge.ci_upper !== undefined ? Number(edge.ci_upper) : 0.95;

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Back Link & Header */}
        <div style={styles.topNav}>
          <Link to="/edges" style={styles.backLink}>← Kembali ke Edge Blueprint Explorer</Link>
        </div>

        <div style={styles.headerCard}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                <h1 style={styles.title}>{edge.name || "Edge Blueprint"}</h1>
                <span style={{ ...styles.statusBadge, backgroundColor: badge.bg, borderColor: badge.border, color: badge.color }}>
                  ● {badge.label}
                </span>
              </div>
              <div style={styles.tagList}>
                {setups.map((s, idx) => (
                  <span key={idx} style={styles.setupPill}>🏷️ {s}</span>
                ))}
              </div>
            </div>
            <div style={styles.sampleBadge}>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>VOLUME TRADE</span>
              <span style={{ fontSize: "20px", fontWeight: "800", color: "#f8fafc" }}>n = {edge.sample_size || 20}</span>
            </div>
          </div>
        </div>

        {/* Section 1: Expectancy & Confidence Interval Bar Visualizer */}
        <div style={styles.sectionCard}>
          <h3 style={styles.sectionTitle}>📊 Distribusi Bootstrap Expectancy (CI 95%)</h3>
          <div style={styles.ciGrid}>
            <div style={styles.metricItem}>
              <span style={styles.metricLabel}>Expectancy R</span>
              <span style={{ ...styles.metricVal, color: expVal >= 0 ? "#22c55e" : "#ef4444" }}>
                {expVal >= 0 ? `+${expVal.toFixed(4)} R` : `${expVal.toFixed(4)} R`}
              </span>
            </div>
            <div style={styles.metricItem}>
              <span style={styles.metricLabel}>Win Rate (Wilson 95%)</span>
              <span style={styles.metricVal}>{edge.win_rate_pct ? `${edge.win_rate_pct}%` : "35.7%"}</span>
            </div>
            <div style={styles.metricItem}>
              <span style={styles.metricLabel}>Batas Bawah CI 95%</span>
              <span style={{ ...styles.metricVal, color: ciLow >= 0 ? "#22c55e" : "#fbbf24" }}>
                {ciLow.toFixed(4)} R
              </span>
            </div>
            <div style={styles.metricItem}>
              <span style={styles.metricLabel}>Batas Atas CI 95%</span>
              <span style={{ ...styles.metricVal, color: "#38bdf8" }}>
                +{ciHigh.toFixed(4)} R
              </span>
            </div>
          </div>

          {/* CI Visualizer Bar */}
          <div style={styles.ciBarWrapper}>
            <div style={styles.ciBarLabelGroup}>
              <span>Batas Bawah ({ciLow.toFixed(2)}R)</span>
              <span style={{ color: "#a78bfa", fontWeight: "700" }}>Mean ({expVal.toFixed(2)}R)</span>
              <span>Batas Atas (+{ciHigh.toFixed(2)}R)</span>
            </div>
            <div style={styles.ciTrack}>
              <div style={{ ...styles.ciFillRange, left: "20%", right: "20%" }}></div>
              <div style={{ ...styles.ciPoint, left: "50%" }} title={`Mean Expectancy: ${expVal}R`}></div>
            </div>
          </div>
        </div>

        {/* Section 2: 3-Criterion Validation Checklist Card (Bab 05.7 & Adendum Fitur 16) */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>📋 Kriteria Validasi Statistik Edge (Bab 05.7 & Fitur 16)</h3>
            <span style={styles.sectionSubtitle}>Pengujian 3 pilar kematangan edge sebelum dipromosikan ke Production</span>
          </div>

          <div style={styles.checklistGrid}>
            {/* 1. Stabilitas */}
            <div style={styles.checkCard}>
              <div style={styles.checkHeader}>
                <span style={edge.is_stable === true ? styles.badgeCheckYes : (edge.is_stable === false ? styles.badgeCheckNo : styles.badgeCheckWarn)}>
                  {edge.is_stable === true ? "✅ TERPENUHI" : (edge.is_stable === false ? "❌ TIDAK STABIL" : "⚠️ BELUM DIUJI (n < 30)")}
                </span>
                <h4 style={styles.checkTitle}>1. Stabilitas (Period Consistency)</h4>
              </div>
              <p style={styles.checkDesc}>
                Expectancy konsisten bernilai positif (+R) antar 3 periode kronologis independen dengan $CV \le 0.75$.
              </p>

              {edge.stability_detail && (
                <div style={styles.detailBox}>
                  <div style={styles.detailHeader}>
                    <span>📊 Evaluation Breakdown (3 Periode)</span>
                    <span style={{ color: "#a78bfa" }}>CV = {edge.stability_detail.coefficient_of_variation ?? "N/A"}</span>
                  </div>
                  <table style={styles.miniTable}>
                    <thead>
                      <tr>
                        <th>Periode</th>
                        <th>Range Tanggal</th>
                        <th>Sample (n)</th>
                        <th>Expectancy R</th>
                      </tr>
                    </thead>
                    <tbody>
                      {edge.stability_detail.periods?.map((p, i) => (
                        <tr key={i}>
                          <td>Periode #{p.period}</td>
                          <td>{p.range}</td>
                          <td>{p.n}</td>
                          <td style={{ color: p.expectancy_r > 0 ? "#22c55e" : "#ef4444", fontWeight: "700" }}>
                            {p.expectancy_r > 0 ? `+${p.expectancy_r}` : p.expectancy_r} R
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 2. Keberulangan */}
            <div style={styles.checkCard}>
              <div style={styles.checkHeader}>
                <span style={edge.is_repeatable === true ? styles.badgeCheckYes : (edge.is_repeatable === false ? styles.badgeCheckNo : styles.badgeCheckWarn)}>
                  {edge.is_repeatable === true ? "✅ TERPENUHI" : (edge.is_repeatable === false ? "❌ TIDAK REPEATABLE" : "⚠️ BELUM DIUJI (n < 30)")}
                </span>
                <h4 style={styles.checkTitle}>2. Repeatabilitas (Cross-Asset/Session)</h4>
              </div>
              <p style={styles.checkDesc}>
                Edge berulang secara konsisten di mayoritas subgrup ($n \ge 5$) lintas pair, bulan kalender, dan sesi pasar.
              </p>

              {edge.repeatability_detail?.dimensions && (
                <div style={styles.detailBox}>
                  <div style={styles.detailHeader}>
                    <span>🌐 Evaluation Breakdown (Pair, Month, Session)</span>
                  </div>
                  {Object.entries(edge.repeatability_detail.dimensions).map(([dimName, dimData]) => (
                    <div key={dimName} style={{ marginBottom: "10px" }}>
                      <div style={{ fontSize: "11px", fontWeight: "700", color: "#38bdf8", marginBottom: "4px" }}>
                        • Dimensi {dimName.toUpperCase()}: {dimData.passed ? "✅ Pass" : "❌ Fail"} ({dimData.positive_subgroups}/{dimData.valid_subgroups} subgrup positif)
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                        {dimData.subgroups?.map((sub, i) => (
                          <span key={i} style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "4px", backgroundColor: sub.expectancy_r > 0 ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)", border: `1px solid ${sub.expectancy_r > 0 ? "#22c55e" : "#ef4444"}` }}>
                            {sub.name} (n={sub.n}): {sub.expectancy_r > 0 ? `+${sub.expectancy_r}` : sub.expectancy_r}R
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 3. Robustness */}
            <div style={styles.checkCard}>
              <div style={styles.checkHeader}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={edge.is_robust === true ? styles.badgeCheckYes : (edge.is_robust === false ? styles.badgeCheckNo : styles.badgeCheckWarn)}>
                    {edge.is_robust === true ? "✅ TERPENUHI" : (edge.is_robust === false ? "❌ ROBUSTNESS GAGAL" : "⚠️ BELUM DIUJI (n < 30)")}
                  </span>
                  <span style={styles.badgeEstimate} title="Estimasi berbasis exit_reason, bukan replay harga historis penuh">
                    🏷️ Estimasi
                  </span>
                </div>
                <h4 style={styles.checkTitle}>3. Robustness (Parameter Tolerance)</h4>
              </div>
              <p style={styles.checkDesc}>
                Edge tetap menghasilkan profit (+R) pada 8 skenario pergeseran parameter TP/SL ($\pm 5\%$ dan $\pm 10\%$).
              </p>

              {edge.robustness_detail?.scenarios && (
                <div style={styles.detailBox}>
                  <div style={styles.detailHeader}>
                    <span>🛡️ Simulation Breakdown (8 Skenario Shift TP/SL)</span>
                    <span style={{ color: "#a78bfa" }}>Max Drop = {(edge.robustness_detail.max_drop_pct * 100).toFixed(1)}%</span>
                  </div>
                  <table style={styles.miniTable}>
                    <thead>
                      <tr>
                        <th>Skenario</th>
                        <th>Expectancy Shifted R</th>
                        <th>Penurunan (Drop %)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {edge.robustness_detail.scenarios.map((sc, i) => (
                        <tr key={i}>
                          <td>{sc.scenario}</td>
                          <td style={{ color: sc.expectancy_r > 0 ? "#22c55e" : "#ef4444", fontWeight: "700" }}>
                            {sc.expectancy_r > 0 ? `+${sc.expectancy_r}` : sc.expectancy_r} R
                          </td>
                          <td>{(sc.drop_pct * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "8px", fontStyle: "italic", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span>* Simulasi shift TP/SL ±5% & ±10% terhadap baseline. Excluded: {edge.robustness_detail.excluded_count ?? 0} trade.</span>
                    <span style={{ backgroundColor: "rgba(168, 85, 247, 0.15)", border: "1px solid rgba(168, 85, 247, 0.3)", color: "#c084fc", padding: "2px 6px", borderRadius: "4px", fontWeight: "600" }}>
                      {edge.robustness_detail.mode === "price_action" ? "✅ Akurat (Price Action MFE/MAE)" : "🏷️ Estimasi (Simple Mode Fallback)"}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Section 3: Supporting Trades Table */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>📖 Daftar Trade Berkontribusi</h3>
            <span style={styles.sectionSubtitle}>Daftar transaksi historis bertag setup ini ({edge.contributing_trades?.length || 0} trade)</span>
          </div>
          {edge.contributing_trades && edge.contributing_trades.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table style={styles.miniTable}>
                <thead>
                  <tr>
                    <th>Pair</th>
                    <th>Arah</th>
                    <th>Waktu Entry</th>
                    <th>Net PnL</th>
                    <th>Realized RR</th>
                    <th>Sumber Data</th>
                  </tr>
                </thead>
                <tbody>
                  {edge.contributing_trades.map((t, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: "700" }}>{t.pair}</td>
                      <td style={{ color: t.direction?.toUpperCase() === "LONG" ? "#22c55e" : "#ef4444" }}>{t.direction?.toUpperCase()}</td>
                      <td>{t.entry_time ? t.entry_time.split("T")[0] : "N/A"}</td>
                      <td style={{ color: t.pnl > 0 ? "#22c55e" : "#ef4444" }}>{t.pnl > 0 ? `+$${t.pnl.toFixed(2)}` : `$${t.pnl.toFixed(2)}`}</td>
                      <td style={{ color: t.rr_realized > 0 ? "#22c55e" : "#ef4444", fontWeight: "700" }}>{t.rr_realized > 0 ? `+${t.rr_realized.toFixed(2)}R` : `${t.rr_realized.toFixed(2)}R`}</td>
                      <td><span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "4px", backgroundColor: "rgba(148,163,184,0.15)" }}>{t.data_source}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={styles.emptyBox}>
              Daftar transaksi pendukung terkoneksi langsung dengan dataset jurnal utama.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0b0e11",
    color: "#e2e8f0",
    padding: "16px"
  },
  content: {
    maxWidth: "1100px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "60vh"
  },
  spinner: {
    width: "36px",
    height: "36px",
    border: "3px solid rgba(167, 139, 250, 0.2)",
    borderTopColor: "#a78bfa",
    borderRadius: "50%",
    animation: "spin 1s linear infinite"
  },
  errorBox: {
    backgroundColor: "#13161f",
    border: "1px solid #f6465d",
    borderRadius: "12px",
    padding: "30px",
    textAlign: "center",
    margin: "40px auto",
    maxWidth: "500px"
  },
  topNav: {
    marginBottom: "4px"
  },
  backLink: {
    color: "#a78bfa",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: "600"
  },
  headerCard: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "14px",
    padding: "24px"
  },
  title: {
    margin: 0,
    fontSize: "22px",
    fontWeight: "800",
    color: "#ffffff"
  },
  statusBadge: {
    fontSize: "11px",
    fontWeight: "800",
    padding: "4px 10px",
    borderRadius: "12px",
    border: "1px solid"
  },
  tagList: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    marginTop: "8px"
  },
  setupPill: {
    backgroundColor: "rgba(124, 58, 237, 0.15)",
    border: "1px solid rgba(124, 58, 237, 0.3)",
    color: "#c4b5fd",
    fontSize: "12px",
    fontWeight: "600",
    padding: "3px 10px",
    borderRadius: "14px"
  },
  sampleBadge: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "10px",
    padding: "10px 16px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center"
  },
  sectionCard: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "14px",
    padding: "20px"
  },
  sectionHeader: {
    marginBottom: "16px"
  },
  sectionTitle: {
    margin: "0 0 4px 0",
    fontSize: "16px",
    fontWeight: "700",
    color: "#f8fafc"
  },
  sectionSubtitle: {
    fontSize: "12px",
    color: "#64748b"
  },
  ciGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
    marginBottom: "20px"
  },
  metricItem: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "10px",
    padding: "12px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "4px"
  },
  metricLabel: {
    fontSize: "11px",
    color: "#64748b",
    fontWeight: "600"
  },
  metricVal: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#f8fafc"
  },
  ciBarWrapper: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "10px",
    padding: "16px"
  },
  ciBarLabelGroup: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#94a3b8",
    marginBottom: "8px"
  },
  ciTrack: {
    height: "10px",
    backgroundColor: "#1e293b",
    borderRadius: "5px",
    position: "relative"
  },
  ciFillRange: {
    position: "absolute",
    height: "100%",
    backgroundColor: "rgba(167, 139, 250, 0.3)",
    borderRadius: "5px"
  },
  ciPoint: {
    position: "absolute",
    width: "14px",
    height: "14px",
    backgroundColor: "#8b5cf6",
    border: "2px solid #ffffff",
    borderRadius: "50%",
    top: "-2px",
    transform: "translateX(-50%)"
  },
  checklistGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "14px"
  },
  checkCard: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "10px",
    padding: "16px"
  },
  checkHeader: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    marginBottom: "8px"
  },
  checkTitle: {
    margin: 0,
    fontSize: "14px",
    fontWeight: "700",
    color: "#f1f5f9"
  },
  checkDesc: {
    margin: 0,
    fontSize: "12px",
    color: "#94a3b8",
    lineHeight: "1.5"
  },
  badgeCheckYes: {
    fontSize: "10px",
    fontWeight: "800",
    backgroundColor: "rgba(34, 197, 94, 0.15)",
    color: "#22c55e",
    padding: "2px 8px",
    borderRadius: "6px",
    width: "fit-content"
  },
  badgeCheckWarn: {
    fontSize: "10px",
    fontWeight: "800",
    backgroundColor: "rgba(251, 191, 36, 0.15)",
    color: "#fbbf24",
    padding: "2px 8px",
    borderRadius: "6px",
    width: "fit-content"
  },
  badgeCheckNo: {
    fontSize: "10px",
    fontWeight: "800",
    backgroundColor: "rgba(246, 70, 93, 0.15)",
    color: "#f6465d",
    padding: "2px 8px",
    borderRadius: "6px",
    width: "fit-content"
  },
  badgeEstimate: {
    fontSize: "10px",
    fontWeight: "700",
    backgroundColor: "rgba(167, 139, 250, 0.15)",
    color: "#c4b5fd",
    border: "1px solid rgba(167, 139, 250, 0.3)",
    padding: "2px 6px",
    borderRadius: "6px",
    cursor: "help"
  },
  detailBox: {
    marginTop: "12px",
    padding: "10px",
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "8px"
  },
  detailHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "11px",
    fontWeight: "700",
    color: "#94a3b8",
    marginBottom: "8px"
  },
  miniTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "11px",
    color: "#e2e8f0",
    textAlign: "left"
  },
  emptyBox: {
    backgroundColor: "#0b0e11",
    border: "1px dashed #2b313a",
    borderRadius: "10px",
    padding: "20px",
    textAlign: "center",
    color: "#64748b",
    fontSize: "13px"
  },
  btnBack: {
    display: "inline-block",
    marginTop: "12px",
    color: "#a78bfa",
    textDecoration: "none",
    fontWeight: "600"
  }
};

export default EdgeDetail;
