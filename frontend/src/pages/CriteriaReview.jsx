import React, { useState, useEffect } from "react";
import { useAuth, API_URL } from "../context/AuthContext";

const CriteriaReview = () => {
  const { getAuthHeader } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchReport();
  }, []);

  const fetchReport = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/edges/criteria-report`, {
        headers: getAuthHeader(),
      });
      if (!response.ok) {
        throw new Error("Gagal mengambil laporan kriteria validasi edge.");
      }
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div style={styles.centerContainer}>Memuat laporan evaluasi kriteria Fitur 16...</div>;
  }

  if (error) {
    return <div style={styles.centerContainer}>❌ Error: {error}</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>📊 Laporan Observasi Ambang Batas Fitur 16</h1>
        <p style={styles.subtitle}>
          Evaluasi nilai mentah Stabilitas (CV), Keberulangan (Subgrup), dan Robustness (Max Drop) untuk kalibrasi ambang batas terhadap data riil.
        </p>
      </div>

      {/* Threshold Reference Card */}
      <div style={styles.thresholdCard}>
        <h3 style={styles.cardTitle}>🎯 Ambang Batas Aktif Sistem:</h3>
        <div style={styles.thresholdGrid}>
          <div style={styles.thresholdItem}>
            <span style={styles.thresholdLabel}>Stabilitas (Max CV):</span>
            <span style={styles.thresholdVal}>≤ 0.75</span>
          </div>
          <div style={styles.thresholdItem}>
            <span style={styles.thresholdLabel}>Keberulangan (Min Subgrup n):</span>
            <span style={styles.thresholdVal}>≥ 5 trade (50% positif)</span>
          </div>
          <div style={styles.thresholdItem}>
            <span style={styles.thresholdLabel}>Robustness (Max Expectancy Drop):</span>
            <span style={styles.thresholdVal}>≤ 50.0%</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={styles.tableCard}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Nama Edge</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Sampel (n)</th>
              <th style={styles.th}>Expectancy</th>
              <th style={styles.th}>CV Stabilitas (≤0.75)</th>
              <th style={styles.th}>Subgrup Positif (≥50%)</th>
              <th style={styles.th}>Max Drop Robustness (≤50%)</th>
              <th style={styles.th}>Kategori Borderline</th>
            </tr>
          </thead>
          <tbody>
            {data && data.edges && data.edges.length > 0 ? (
              data.edges.map((edge) => {
                const isBorderline = edge.borderline_score < 0.2;
                return (
                  <tr key={edge.id} style={styles.tr}>
                    <td style={styles.tdBold}>{edge.name}</td>
                    <td style={styles.td}>
                      <span style={styles.statusBadge(edge.status)}>{edge.status.toUpperCase()}</span>
                    </td>
                    <td style={styles.td}>{edge.sample_size}</td>
                    <td style={styles.td}>{edge.expectancy_r.toFixed(2)} R</td>
                    <td style={styles.tdVal(edge.is_stable)}>
                      {edge.stability_cv.toFixed(3)} {edge.is_stable ? "✅" : "❌"}
                    </td>
                    <td style={styles.tdVal(edge.is_repeatable)}>
                      {edge.repeatability_pct_positive.toFixed(1)}% ({edge.repeatability_valid_subgroups} subgrup) {edge.is_repeatable ? "✅" : "❌"}
                    </td>
                    <td style={styles.tdVal(edge.is_robust)}>
                      {edge.robustness_max_drop_pct.toFixed(1)}% {edge.is_robust ? "✅" : "❌"}
                    </td>
                    <td style={styles.td}>
                      {isBorderline ? (
                        <span style={styles.borderlineBadge}>⚠️ Nyaris Ambang ({edge.borderline_score.toFixed(2)})</span>
                      ) : (
                        <span style={styles.normalBadge}>Stabil/Jauh</span>
                      )}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan="8" style={styles.emptyTd}>
                  Belum ada Edge Blueprint dengan n ≥ 30 untuk dievaluasi.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: "30px",
    backgroundColor: "#0d0a1b",
    color: "#e2e8f0",
    minHeight: "100vh",
    fontFamily: "'Inter', sans-serif",
  },
  centerContainer: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    backgroundColor: "#0d0a1b",
    color: "#e2e8f0",
    fontSize: "18px",
  },
  header: {
    marginBottom: "24px",
  },
  title: {
    fontSize: "24px",
    fontWeight: "700",
    color: "#ffffff",
    margin: "0 0 8px 0",
  },
  subtitle: {
    fontSize: "14px",
    color: "#94a3b8",
    margin: 0,
  },
  thresholdCard: {
    backgroundColor: "rgba(22, 19, 39, 0.7)",
    borderRadius: "12px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    padding: "20px",
    marginBottom: "24px",
  },
  cardTitle: {
    fontSize: "16px",
    fontWeight: "600",
    color: "#a7f3d0",
    margin: "0 0 12px 0",
  },
  thresholdGrid: {
    display: "flex",
    gap: "30px",
  },
  thresholdItem: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  thresholdLabel: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  thresholdVal: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#ffffff",
  },
  tableCard: {
    backgroundColor: "rgba(22, 19, 39, 0.7)",
    borderRadius: "12px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    overflow: "hidden",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    textAlign: "left",
  },
  th: {
    padding: "14px 18px",
    backgroundColor: "rgba(30, 27, 50, 0.8)",
    color: "#cbd5e1",
    fontSize: "13px",
    fontWeight: "600",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  },
  tr: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
  },
  td: {
    padding: "14px 18px",
    fontSize: "13px",
    color: "#e2e8f0",
  },
  tdBold: {
    padding: "14px 18px",
    fontSize: "13px",
    fontWeight: "600",
    color: "#ffffff",
  },
  tdVal: (passed) => ({
    padding: "14px 18px",
    fontSize: "13px",
    fontWeight: "600",
    color: passed ? "#34d399" : "#f87171",
  }),
  statusBadge: (status) => {
    const colors = {
      production: { bg: "rgba(16, 185, 129, 0.15)", border: "rgba(16, 185, 129, 0.3)", text: "#34d399" },
      validation: { bg: "rgba(59, 130, 246, 0.15)", border: "rgba(59, 130, 246, 0.3)", text: "#60a5fa" },
      monitoring: { bg: "rgba(239, 68, 68, 0.15)", border: "rgba(239, 68, 68, 0.3)", text: "#f87171" },
      research: { bg: "rgba(245, 158, 11, 0.15)", border: "rgba(245, 158, 11, 0.3)", text: "#fbbf24" },
    };
    const c = colors[status] || colors.research;
    return {
      padding: "4px 8px",
      borderRadius: "4px",
      fontSize: "11px",
      fontWeight: "700",
      backgroundColor: c.bg,
      border: `1px solid ${c.border}`,
      color: c.text,
    };
  },
  borderlineBadge: {
    padding: "4px 8px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: "600",
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    border: "1px solid rgba(245, 158, 11, 0.3)",
    color: "#fbbf24",
  },
  normalBadge: {
    fontSize: "12px",
    color: "#64748b",
  },
  emptyTd: {
    padding: "40px",
    textAlign: "center",
    color: "#94a3b8",
    fontSize: "14px",
  },
};

export default CriteriaReview;
