import React from "react";

const RDistributionChart = ({ distribution = [] }) => {
  if (!distribution || distribution.length === 0) {
    return (
      <div style={styles.card}>
        <h3 style={styles.title}>📊 Distribusi R-Multiple</h3>
        <p style={styles.emptyText}>Belum ada data distribusi trade.</p>
      </div>
    );
  }

  const maxCount = Math.max(...distribution.map((d) => d.count), 1);

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <h3 style={styles.title}>📊 Distribusi Realized R-Multiple (Histogram)</h3>
        <span style={styles.subtitle}>Frekuensi sebaran hasil R dari seluruh closed trade</span>
      </div>

      <div style={styles.chartArea}>
        {distribution.map((item, idx) => {
          const barHeightPct = (item.count / maxCount) * 100;
          return (
            <div key={idx} style={styles.barColumn}>
              <span style={styles.barCount}>{item.count}</span>
              <div style={styles.barTrack}>
                <div
                  style={{
                    ...styles.barFill,
                    height: `${Math.max(barHeightPct, 6)}%`,
                    backgroundColor: item.color,
                  }}
                  title={`${item.label}: ${item.count} trade (${item.percentage}%)`}
                />
              </div>
              <span style={styles.barLabel}>{item.label}</span>
              <span style={styles.barPct}>{item.percentage}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const styles = {
  card: {
    backgroundColor: "#181a20",
    border: "1px solid #2b313a",
    borderRadius: "16px",
    padding: "20px",
    marginBottom: "24px",
    color: "#eaecef",
  },
  header: {
    marginBottom: "20px",
  },
  title: {
    fontSize: "16px",
    fontWeight: "700",
    color: "#ffffff",
    margin: 0,
  },
  subtitle: {
    fontSize: "12px",
    color: "#848e9c",
  },
  chartArea: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    height: "220px",
    gap: "12px",
    paddingTop: "20px",
    paddingBottom: "10px",
    borderBottom: "1px solid #2b313a",
  },
  barColumn: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    height: "100%",
  },
  barCount: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: "6px",
  },
  barTrack: {
    flex: 1,
    width: "100%",
    maxWidth: "40px",
    backgroundColor: "#0b0e11",
    borderRadius: "6px",
    display: "flex",
    alignItems: "flex-end",
    overflow: "hidden",
    border: "1px solid #2b313a",
  },
  barFill: {
    width: "100%",
    borderRadius: "4px",
    transition: "height 0.3s ease-in-out",
  },
  barLabel: {
    fontSize: "11px",
    fontWeight: "600",
    color: "#cbd5e1",
    marginTop: "8px",
    textAlign: "center",
  },
  barPct: {
    fontSize: "10px",
    color: "#848e9c",
  },
  emptyText: {
    color: "#848e9c",
    fontSize: "13px",
  },
};

export default RDistributionChart;
