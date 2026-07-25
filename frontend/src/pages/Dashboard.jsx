import React from "react";
import { Link } from "react-router-dom";
import EquityCurveChart from "../components/EquityCurveChart";

const Dashboard = () => {
  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Header */}
        <div style={styles.headerRow}>
          <div>
            <h1 style={styles.title}>Dasbor Performa & Layanan Ekuitas</h1>
            <p style={styles.subtitle}>
              Pantau pertumbuhan saldo akun riil Binance dan kualitas keputusan trading murni secara real-time.
            </p>
          </div>
          <div style={styles.actionGroup}>
            <Link to="/quick-tag" style={styles.btnPrimary}>
              ⚡ Quick-Tag (&lt; 15s)
            </Link>
            <Link to="/journal" style={styles.btnSecondary}>
              📖 Lihat Jurnal Trade
            </Link>
            <Link to="/import-wizard" style={styles.btnSecondary}>
              🔄 Wizard Impor Historis
            </Link>
          </div>
        </div>

        {/* Equity Snapshot & Dual-Line Curve Section */}
        <EquityCurveChart />
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
