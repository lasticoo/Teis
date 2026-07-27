import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import EquityCurveChart from "../components/EquityCurveChart";
import AnalyticsSummaryCards from "../components/AnalyticsSummaryCards";
import RDistributionChart from "../components/RDistributionChart";

const Dashboard = () => {
  const [filterSource, setFilterSource] = useState("live"); // Default to Live Trade
  const [filterPair, setFilterPair] = useState("all");
  const [filterSession, setFilterSession] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [analyticsSummary, setAnalyticsSummary] = useState(null);
  const [rDistribution, setRDistribution] = useState([]);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchAnalyticsData = async (source, pair = "all", session = "all", start = "", end = "") => {
    setLoadingAnalytics(true);
    try {
      let queryParams = `filter_source=${source}&filter_pair=${pair}&filter_session=${session}`;
      if (start) queryParams += `&start_date=${start}`;
      if (end) queryParams += `&end_date=${end}`;

      const [sumRes, distRes] = await Promise.all([
        fetch(`http://localhost:8000/api/v1/analytics/summary?${queryParams}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`http://localhost:8000/api/v1/analytics/distribution?${queryParams}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setAnalyticsSummary(sumData);
      }

      if (distRes.ok) {
        const distData = await distRes.json();
        setRDistribution(distData.distribution || []);
      }
    } catch (err) {
      console.error("Gagal mengambil data Mesin Analitis:", err);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  useEffect(() => {
    fetchAnalyticsData(filterSource, filterPair, filterSession, startDate, endDate);
  }, [filterSource, filterPair, filterSession, startDate, endDate]);

  const handleResetDates = () => {
    setStartDate("");
    setEndDate("");
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.headerRow}>
          <div style={styles.titleGroup}>
            <div style={styles.badgePill}>
              <span style={styles.badgeDot}></span> TEIS Performance Engine
            </div>
            <h1 style={styles.title}>Dasbor Performa Trading</h1>
          </div>
          <div style={styles.actionGroup}>
            <Link to="/quick-tag" style={styles.btnPrimary}>
              ⚡ Quick-Tag (&lt; 15s)
            </Link>
            <Link to="/journal" style={styles.btnSecondary}>
              📖 Lihat Jurnal
            </Link>
            <Link to="/import" style={styles.btnSecondary}>
              🔄 Wizard Impor
            </Link>
          </div>
        </div>

        {/* Date Range Picker Bar */}
        <div style={styles.datePickerBar}>
          <div style={styles.dateGroup}>
            <label style={styles.dateLabel}>📅 Dari Tanggal:</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={styles.dateInput}
            />
          </div>
          <div style={styles.dateGroup}>
            <label style={styles.dateLabel}>📅 Sampai Tanggal:</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={styles.dateInput}
            />
          </div>
          {(startDate || endDate) && (
            <button onClick={handleResetDates} style={styles.btnReset}>
              ✕ Reset Tanggal
            </button>
          )}
        </div>

        {/* Analytics Engine Headline Cards & Source Filter */}
        <AnalyticsSummaryCards
          summary={analyticsSummary || {}}
          filterSource={filterSource}
          onFilterSourceChange={setFilterSource}
          filterPair={filterPair}
          onFilterPairChange={setFilterPair}
          filterSession={filterSession}
          onFilterSessionChange={setFilterSession}
        />

        {/* Equity Snapshot & Dual-Line Curve Section */}
        <EquityCurveChart startDate={startDate} endDate={endDate} />

        {/* R-Multiple Distribution Histogram */}
        <RDistributionChart distribution={rDistribution} />
      </div>
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0b0e11",
    color: "#e2e8f0",
    padding: "0",
  },
  content: {
    maxWidth: "1200px",
    margin: "0 auto",
  },
  headerRow: {
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
    gap: "6px",
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
    width: "fit-content",
    letterSpacing: "0.5px",
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
  actionGroup: {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
  },
  btnPrimary: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    padding: "10px 18px",
    borderRadius: "10px",
    fontSize: "13px",
    fontWeight: "700",
    textDecoration: "none",
    boxShadow: "0 4px 14px rgba(124, 58, 237, 0.4)",
    transition: "all 0.2s",
  },
  btnSecondary: {
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    color: "#e2e8f0",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    padding: "10px 18px",
    borderRadius: "10px",
    fontSize: "13px",
    fontWeight: "600",
    textDecoration: "none",
    transition: "all 0.2s",
  },
  datePickerBar: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "12px",
    padding: "14px 18px",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    flexWrap: "wrap",
    marginBottom: "20px"
  },
  dateGroup: {
    display: "flex",
    alignItems: "center",
    gap: "8px"
  },
  dateLabel: {
    fontSize: "12.5px",
    fontWeight: "600",
    color: "#94a3b8"
  },
  dateInput: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e293b",
    color: "#f8fafc",
    padding: "6px 12px",
    borderRadius: "8px",
    fontSize: "13px",
    outline: "none"
  },
  btnReset: {
    backgroundColor: "rgba(246, 70, 93, 0.15)",
    color: "#f6465d",
    border: "1px solid rgba(246, 70, 93, 0.3)",
    padding: "6px 12px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer"
  }
};

export default Dashboard;
