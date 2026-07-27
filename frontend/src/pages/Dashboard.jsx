import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import EquityCurveChart from "../components/EquityCurveChart";
import AnalyticsSummaryCards from "../components/AnalyticsSummaryCards";
import RDistributionChart from "../components/RDistributionChart";

const Dashboard = () => {
  const [filterSource, setFilterSource] = useState("all");
  const [filterPair, setFilterPair] = useState("all");
  const [filterSession, setFilterSession] = useState("all");

  const [analyticsSummary, setAnalyticsSummary] = useState(null);
  const [rDistribution, setRDistribution] = useState([]);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchAnalyticsData = async (source, pair = "all", session = "all") => {
    setLoadingAnalytics(true);
    try {
      const [sumRes, distRes] = await Promise.all([
        fetch(`http://localhost:8000/api/v1/analytics/summary?filter_source=${source}&filter_pair=${pair}&filter_session=${session}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`http://localhost:8000/api/v1/analytics/distribution?filter_source=${source}&filter_pair=${pair}&filter_session=${session}`, {
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
    fetchAnalyticsData(filterSource, filterPair, filterSession);
  }, [filterSource, filterPair, filterSession]);

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
            <Link to="/import-wizard" style={styles.btnSecondary}>
              🔄 Wizard Impor
            </Link>
          </div>
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
        <EquityCurveChart />

        {/* R-Multiple Distribution Histogram */}
        <RDistributionChart distribution={rDistribution} />
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
    maxWidth: "1200px",
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
};

export default Dashboard;
