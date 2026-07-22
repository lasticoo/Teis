import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import MarketContextCard from "../components/MarketContextCard";
import CorrectionModal from "../components/CorrectionModal";

const TradeDetail = () => {
  const { tradeId } = useParams();
  const navigate = useNavigate();
  const [trade, setTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [zoomedImage, setZoomedImage] = useState(null);
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);

  const fetchTradeDetail = async () => {
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/journal/detail/${tradeId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        if (res.status === 404) {
          throw new Error("Trade tidak ditemukan.");
        }
        throw new Error(`HTTP ${res.status}: Gagal mengambil rincian detail trade.`);
      }

      const data = await res.json();
      setTrade(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tradeId) {
      fetchTradeDetail();
    }
  }, [tradeId]);

  const formatHoldingTime = (sec) => {
    if (sec === null || sec === undefined) return "—";
    if (sec < 60) return `${sec} detik`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}d`;
    const hours = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    return `${hours} jam ${mins} menit`;
  };

  const getSetupStyle = (tag) => {
    if (tag.includes("H4")) {
      return {
        background: "rgba(59, 130, 246, 0.2)",
        color: "#60a5fa",
        border: "1px solid rgba(59, 130, 246, 0.35)",
        padding: "4px 10px",
        borderRadius: "6px",
        fontSize: "12px",
        fontWeight: "700",
      };
    }
    if (tag.includes("H1")) {
      return {
        background: "rgba(16, 185, 129, 0.2)",
        color: "#34d399",
        border: "1px solid rgba(16, 185, 129, 0.35)",
        padding: "4px 10px",
        borderRadius: "6px",
        fontSize: "12px",
        fontWeight: "700",
      };
    }
    if (tag.includes("FIBONACCI")) {
      return {
        background: "rgba(245, 158, 11, 0.2)",
        color: "#fbbf24",
        border: "1px solid rgba(245, 158, 11, 0.35)",
        padding: "4px 10px",
        borderRadius: "6px",
        fontSize: "12px",
        fontWeight: "700",
      };
    }
    return {
      background: "rgba(168, 85, 247, 0.2)",
      color: "#c084fc",
      border: "1px solid rgba(168, 85, 247, 0.35)",
      padding: "4px 10px",
      borderRadius: "6px",
      fontSize: "12px",
      fontWeight: "700",
    };
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingWrapper}>
          <div style={styles.spinner} />
          <p style={styles.loadingText}>Memuat rincian detail trade...</p>
        </div>
      </div>
    );
  }

  if (error || !trade) {
    return (
      <div style={styles.container}>
        <div style={styles.errorCard}>
          <h2>⚠️ Gagal Memuat Detail Trade</h2>
          <p>{error || "Data trade tidak dapat ditemukan."}</p>
          <button onClick={() => navigate("/journal")} style={styles.backBtn}>
            ← Kembali ke Daftar Jurnal
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Navigation Bar */}
        <div style={styles.navRow}>
          <button onClick={() => navigate("/journal")} style={styles.backBtn}>
            ← Kembali ke Daftar Jurnal
          </button>
          <span style={styles.breadcrumb}>Jurnal / Trade ID: {trade.id}</span>
        </div>

        {/* Trade Header */}
        <div style={styles.tradeHeaderCard}>
          <div style={styles.headerLeft}>
            <div style={styles.titleBadgeRow}>
              <h1 style={styles.tradeTitle}>{trade.pair}</h1>
              <span style={trade.direction === "long" ? styles.badgeLong : styles.badgeShort}>
                {trade.direction.toUpperCase()}
              </span>
              <span style={trade.source_badge === "Live" ? styles.badgeLive : styles.badgeImport}>
                {trade.source_badge}
              </span>
              <span style={trade.status === "Closed" ? styles.badgeClosed : styles.badgeOpen}>
                {trade.status}
              </span>
              {trade.is_locked && <span style={styles.badgeLocked}>🔒 Terkunci</span>}
            </div>
            <span style={styles.subText}>
              Entry Time: {new Date(trade.entry_time).toLocaleString()}
              {trade.exit_time && ` | Exit Time: ${new Date(trade.exit_time).toLocaleString()}`}
            </span>
          </div>

          <div style={styles.headerRight}>
            <div style={styles.pnlHeaderCard}>
              <span style={styles.pnlHeaderLabel}>NET PnL</span>
              <span style={{
                ...styles.pnlHeaderValue,
                color: trade.pnl === null ? "#94a3b8" : trade.pnl >= 0 ? "#22c55e" : "#ef4444"
              }}>
                {trade.pnl === null ? "—" : trade.pnl >= 0 ? `+$${trade.pnl.toFixed(2)}` : `-$${Math.abs(trade.pnl).toFixed(2)}`}
              </span>
            </div>
            {trade.is_locked && (
              <button
                onClick={() => setIsCorrectionModalOpen(true)}
                style={styles.correctBtn}
              >
                📝 Ajukan Koreksi
              </button>
            )}
          </div>
        </div>

        {/* Summary Metric Cards */}
        <div style={styles.metricGrid}>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>ENTRY VWAP</span>
            <span style={styles.metricValue}>${trade.entry_price.toFixed(4)}</span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>EXIT VWAP</span>
            <span style={styles.metricValue}>
              {trade.exit_price ? `$${trade.exit_price.toFixed(4)}` : "—"}
            </span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>REALIZED RR</span>
            <span style={{
              ...styles.metricValue,
              color: trade.rr_realized === null ? "#ffffff" : trade.rr_realized >= 0 ? "#22c55e" : "#ef4444"
            }}>
              {trade.rr_realized !== null ? `${trade.rr_realized.toFixed(2)}R` : "—"}
            </span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>TOTAL FEE</span>
            <span style={styles.metricValue}>
              {trade.fee !== null ? `$${trade.fee.toFixed(4)}` : "—"}
            </span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>HOLDING TIME</span>
            <span style={styles.metricValue}>{formatHoldingTime(trade.holding_time_sec)}</span>
          </div>
        </div>

        {/* Section 1: Fill Eksekusi Binance */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>⚡ Fill Eksekusi Binance Terhubung ({trade.fills.length})</h3>
            <span style={styles.sectionSubtitle}>Daftar eksekusi pasar asli dari Binance Futures API</span>
          </div>
          {trade.fills.length === 0 ? (
            <div style={styles.emptyBox}>Tidak ada fills eksekusi Binance terhubung.</div>
          ) : (
            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>ROLE</th>
                    <th style={styles.th}>BINANCE TRADE ID</th>
                    <th style={styles.th}>SIDE</th>
                    <th style={styles.th}>HARGA (PX)</th>
                    <th style={styles.th}>KUANTITAS (QTY)</th>
                    <th style={styles.th}>FEE</th>
                    <th style={styles.th}>WAKTU EKSEKUSI (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {trade.fills.map((f) => (
                    <tr key={f.id} style={styles.tr}>
                      <td style={styles.td}>
                        <span style={f.role === "entry" ? styles.badgeEntry : styles.badgeExit}>
                          {f.role.toUpperCase()}
                        </span>
                      </td>
                      <td style={styles.tdCode}>{f.binance_trade_id}</td>
                      <td style={styles.td}>
                        <span style={f.side === "BUY" ? styles.badgeLong : styles.badgeShort}>
                          {f.side}
                        </span>
                      </td>
                      <td style={styles.tdNum}>${f.price.toFixed(4)}</td>
                      <td style={styles.tdNum}>{f.qty}</td>
                      <td style={styles.tdNum}>${f.fee.toFixed(5)}</td>
                      <td style={styles.td}>
                        {f.executed_at ? new Date(f.executed_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {/* Trade Execution Parameters */}
          {trade.execution && (
            <div style={styles.execContainer}>
              <h4 style={styles.subCardTitle}>⚙️ Parameter Eksekusi & Manajemen Risiko</h4>
              <div style={styles.execCardGrid}>
                <div style={styles.execCardItem}>
                  <span style={styles.execLabel}>Tipe Order:</span>
                  <span style={styles.execValue}>{trade.execution.order_type.toUpperCase()}</span>
                </div>
                <div style={styles.execCardItem}>
                  <span style={styles.execLabel}>Moved to Breakeven (BE):</span>
                  <span style={trade.execution.moved_to_breakeven ? styles.badgePlanYes : styles.badgePlanNo}>
                    {trade.execution.moved_to_breakeven ? "YA" : "TIDAK"}
                  </span>
                </div>
                <div style={styles.execCardItem}>
                  <span style={styles.execLabel}>Trailing Stop Used:</span>
                  <span style={trade.execution.trailing_stop_used ? styles.badgePlanYes : styles.badgePlanNo}>
                    {trade.execution.trailing_stop_used ? "YA" : "TIDAK"}
                  </span>
                </div>
                <div style={styles.execCardItem}>
                  <span style={styles.execLabel}>Alasan Exit:</span>
                  <span style={styles.execValue}>{trade.execution.exit_reason || "—"}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 2: Tag Subjektif & Psikologi */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>🏷️ Tagging Subjektif & Psikologi Trader</h3>
            <span style={styles.sectionSubtitle}>Hasil pengisian Quick-Tag terstruktur dan kondisi emosi saat entry</span>
          </div>

          <div style={styles.gridTwoCols}>
            {/* Setup Tags */}
            <div style={styles.subCard}>
              <h4 style={styles.subCardTitle}>Model Setup & Konfirmasi Terpilih</h4>
              {trade.setups.length === 0 ? (
                <span style={styles.dimText}>Belum ada tag setup yang diisi.</span>
              ) : (
                <div style={styles.setupContainer}>
                  {trade.setups.map((s, idx) => (
                    <span key={idx} style={getSetupStyle(s)}>{s}</span>
                  ))}
                </div>
              )}
            </div>

            {/* Psikologi & Plan */}
            <div style={styles.subCard}>
              <h4 style={styles.subCardTitle}>Psikologi & Kepatuhan Plan</h4>
              {trade.psychology ? (
                <div style={styles.psyDetails}>
                  <div style={styles.psyRow}>
                    <span style={styles.psyLabel}>Confidence Level:</span>
                    <span style={styles.psyVal}>{trade.psychology.confidence_level}/10</span>
                  </div>
                  <div style={styles.psyRow}>
                    <span style={styles.psyLabel}>Kepatuhan Plan:</span>
                    <span style={trade.psychology.plan_adherence ? styles.badgePlanYes : styles.badgePlanNo}>
                      {trade.psychology.plan_adherence ? "YA (Patuh Plan)" : "TIDAK (Impulsif)"}
                    </span>
                  </div>
                  <div style={styles.psyRow}>
                    <span style={styles.psyLabel}>Kondisi Emosional:</span>
                    <div style={styles.emoTags}>
                      {trade.psychology.psychological_tags && trade.psychology.psychological_tags.length > 0 ? (
                        trade.psychology.psychological_tags.map((emo, idx) => (
                          <span key={idx} style={styles.emoPill}>{emo}</span>
                        ))
                      ) : (
                        <span style={styles.dimText}>—</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <span style={styles.dimText}>Data psikologi belum diisi.</span>
              )}
            </div>
          </div>
        </div>

        {/* Section 3: Market Context Collector (Objektif) */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>🌍 Konteks Pasar Objektif (Market Context Collector)</h3>
            <span style={styles.sectionSubtitle}>Snapshot kondisi makro crypto saat entry trade</span>
          </div>
          <MarketContextCard contextData={trade.market_context} tradeId={trade.id} />
        </div>

        {/* Section 4: Screenshot & Catatan */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>🖼️ Screenshot Chart & Catatan Tambahan</h3>
            <span style={styles.sectionSubtitle}>Bukti visual setup chart sebelum entry dan catatan analisis</span>
          </div>

          <div style={styles.gridTwoCols}>
            {/* Screenshot */}
            <div style={styles.subCard}>
              <h4 style={styles.subCardTitle}>Screenshot Chart Sebelum Entry</h4>
              {trade.screenshots && trade.screenshots.length > 0 ? (
                <div style={styles.screenshotGrid}>
                  {trade.screenshots.map((sc) => (
                    <div key={sc.id} style={styles.screenshotBox} onClick={() => setZoomedImage(sc.url)}>
                      <img src={sc.url} alt="Chart Screenshot" style={styles.screenshotImg} />
                      <span style={styles.zoomHint}>🔍 Klik untuk Zoom Gambar</span>
                    </div>
                  ))}
                </div>
              ) : (
                <span style={styles.dimText}>Tidak ada screenshot chart yang diupload.</span>
              )}
            </div>

            {/* Notes */}
            <div style={styles.subCard}>
              <h4 style={styles.subCardTitle}>Catatan Bebas Trader</h4>
              <p style={styles.freeNotesText}>
                {trade.psychology?.free_notes || "Tidak ada catatan bebas untuk trade ini."}
              </p>
            </div>
          </div>
        </div>

        {/* Section 5: Audit Log Koreksi (trade_corrections) */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>📋 Audit Log Koreksi Trade (`trade_corrections`)</h3>
            <span style={styles.sectionSubtitle}>
              Histori resmi koreksi data pasca-penguncian imutabilitas database
            </span>
          </div>

          {trade.corrections && trade.corrections.length > 0 ? (
            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>FIELD DIKOREKSI</th>
                    <th style={styles.th}>NILAI LAMA</th>
                    <th style={styles.th}>NILAI BARU</th>
                    <th style={styles.th}>ALASAN KOREKSI</th>
                    <th style={styles.th}>WAKTU KOREKSI</th>
                  </tr>
                </thead>
                <tbody>
                  {trade.corrections.map((c) => (
                    <tr key={c.id} style={styles.tr}>
                      <td style={styles.td}>
                        <span style={styles.auditFieldPill}>{c.field_name}</span>
                      </td>
                      <td style={styles.tdCode}>{c.old_value || "—"}</td>
                      <td style={{ ...styles.tdCode, color: "#34d399", fontWeight: "700" }}>
                        {c.new_value || "—"}
                      </td>
                      <td style={styles.tdReason}>{c.reason}</td>
                      <td style={styles.td}>
                        {c.corrected_at ? new Date(c.corrected_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span style={styles.dimText}>Belum ada riwayat koreksi data pada trade ini.</span>
          )}
        </div>
      </div>

      {/* Image Zoom Modal */}
      {zoomedImage && (
        <div style={styles.modalOverlay} onClick={() => setZoomedImage(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <img src={zoomedImage} alt="Zoomed Chart" style={styles.zoomedImg} />
            <button onClick={() => setZoomedImage(null)} style={styles.closeModalBtn}>
              ✕ Tutup Zoom
            </button>
          </div>
        </div>
      )}

      {/* Correction Form Modal */}
      <CorrectionModal
        isOpen={isCorrectionModalOpen}
        onClose={() => setIsCorrectionModalOpen(false)}
        trade={trade}
        onSuccess={fetchTradeDetail}
      />
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0b0914",
    color: "#ffffff",
    fontFamily: "'Inter', sans-serif",
    padding: "30px 20px",
  },
  content: {
    maxWidth: "1200px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  navRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  backBtn: {
    backgroundColor: "rgba(124, 58, 237, 0.15)",
    border: "1px solid #7c3aed",
    color: "#ffffff",
    padding: "8px 16px",
    borderRadius: "8px",
    fontWeight: "700",
    fontSize: "13px",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  breadcrumb: {
    fontSize: "12px",
    color: "#64748b",
  },
  tradeHeaderCard: {
    backgroundColor: "rgba(22, 19, 39, 0.7)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: "14px",
    padding: "24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "20px",
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  titleBadgeRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
  },
  tradeTitle: {
    fontSize: "26px",
    fontWeight: "800",
    margin: 0,
  },
  subText: {
    fontSize: "13px",
    color: "#94a3b8",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: "20px",
  },
  pnlHeaderCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
  },
  correctBtn: {
    backgroundColor: "rgba(124, 58, 237, 0.2)",
    border: "1px solid #7c3aed",
    color: "#ffffff",
    padding: "10px 18px",
    borderRadius: "8px",
    fontWeight: "700",
    fontSize: "13px",
    cursor: "pointer",
    boxShadow: "0 4px 15px rgba(124, 58, 237, 0.25)",
    transition: "all 0.2s ease",
  },
  execContainer: {
    marginTop: "16px",
    paddingTop: "16px",
    borderTop: "1px solid rgba(255, 255, 255, 0.08)",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  execCardGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "12px",
  },
  execCardItem: {
    backgroundColor: "rgba(15, 12, 30, 0.5)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    borderRadius: "8px",
    padding: "12px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  execLabel: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  execValue: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#ffffff",
  },
  tdReason: {
    padding: "12px 14px",
    fontSize: "12px",
    color: "#cbd5e1",
    lineHeight: "1.4",
    maxWidth: "350px",
  },
  auditFieldPill: {
    backgroundColor: "rgba(59, 130, 246, 0.15)",
    color: "#60a5fa",
    border: "1px solid rgba(59, 130, 246, 0.3)",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
  },
  pnlHeaderLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: "0.5px",
  },
  pnlHeaderValue: {
    fontSize: "28px",
    fontWeight: "800",
  },
  badgeLong: {
    backgroundColor: "rgba(34, 197, 94, 0.15)",
    color: "#22c55e",
    border: "1px solid rgba(34, 197, 94, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "800",
  },
  badgeShort: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    color: "#ef4444",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "800",
  },
  badgeLive: {
    backgroundColor: "rgba(34, 197, 94, 0.15)",
    color: "#22c55e",
    border: "1px solid rgba(34, 197, 94, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
  },
  badgeImport: {
    backgroundColor: "rgba(168, 85, 247, 0.15)",
    color: "#a855f7",
    border: "1px solid rgba(168, 85, 247, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
  },
  badgeOpen: {
    backgroundColor: "rgba(59, 130, 246, 0.15)",
    color: "#60a5fa",
    border: "1px solid rgba(59, 130, 246, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
  },
  badgeClosed: {
    backgroundColor: "rgba(148, 163, 184, 0.15)",
    color: "#94a3b8",
    border: "1px solid rgba(148, 163, 184, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
  },
  badgeLocked: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    color: "#f59e0b",
    border: "1px solid rgba(245, 158, 11, 0.3)",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "700",
  },
  metricGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "16px",
  },
  metricCard: {
    backgroundColor: "rgba(22, 19, 39, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: "12px",
    padding: "18px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  metricLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: "0.5px",
  },
  metricValue: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#ffffff",
  },
  sectionCard: {
    backgroundColor: "rgba(22, 19, 39, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: "14px",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  sectionHeader: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
    paddingBottom: "12px",
  },
  sectionTitle: {
    fontSize: "16px",
    fontWeight: "800",
    margin: 0,
  },
  sectionSubtitle: {
    fontSize: "12px",
    color: "#64748b",
  },
  tableWrapper: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    textAlign: "left",
  },
  th: {
    padding: "12px 14px",
    fontSize: "11px",
    fontWeight: "700",
    color: "#64748b",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  },
  tr: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
  },
  td: {
    padding: "12px 14px",
    fontSize: "13px",
  },
  tdCode: {
    padding: "12px 14px",
    fontSize: "12px",
    fontFamily: "monospace",
    color: "#cbd5e1",
  },
  tdNum: {
    padding: "12px 14px",
    fontSize: "13px",
    fontVariantNumeric: "tabular-nums",
  },
  badgeEntry: {
    backgroundColor: "rgba(59, 130, 246, 0.15)",
    color: "#60a5fa",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "700",
  },
  badgeExit: {
    backgroundColor: "rgba(168, 85, 247, 0.15)",
    color: "#c084fc",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "700",
  },
  gridTwoCols: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: "20px",
  },
  subCard: {
    backgroundColor: "rgba(15, 12, 30, 0.5)",
    border: "1px solid rgba(255, 255, 255, 0.05)",
    borderRadius: "10px",
    padding: "18px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  subCardTitle: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#cbd5e1",
    margin: 0,
  },
  setupContainer: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  psyDetails: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  psyRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: "13px",
  },
  psyLabel: {
    color: "#94a3b8",
  },
  psyVal: {
    fontWeight: "700",
    color: "#ffffff",
  },
  badgePlanYes: {
    backgroundColor: "rgba(34, 197, 94, 0.2)",
    color: "#22c55e",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
  },
  badgePlanNo: {
    backgroundColor: "rgba(239, 68, 68, 0.2)",
    color: "#ef4444",
    padding: "3px 8px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
  },
  emoTags: {
    display: "flex",
    gap: "6px",
    flexWrap: "wrap",
  },
  emoPill: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    color: "#e2e8f0",
    padding: "2px 8px",
    borderRadius: "12px",
    fontSize: "11px",
  },
  dimText: {
    color: "#64748b",
    fontSize: "13px",
  },
  screenshotGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  screenshotBox: {
    position: "relative",
    borderRadius: "8px",
    overflow: "hidden",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    cursor: "pointer",
  },
  screenshotImg: {
    width: "100%",
    maxHeight: "250px",
    objectFit: "cover",
    display: "block",
  },
  zoomHint: {
    position: "absolute",
    bottom: "8px",
    right: "8px",
    backgroundColor: "rgba(0,0,0,0.7)",
    color: "#ffffff",
    padding: "4px 8px",
    borderRadius: "4px",
    fontSize: "11px",
  },
  freeNotesText: {
    fontSize: "13px",
    lineHeight: "1.6",
    color: "#cbd5e1",
    margin: 0,
    whiteSpace: "pre-wrap",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.85)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 9999,
    padding: "20px",
  },
  modalContent: {
    position: "relative",
    maxWidth: "90vw",
    maxHeight: "90vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
  },
  zoomedImg: {
    maxWidth: "100%",
    maxHeight: "80vh",
    borderRadius: "8px",
    boxShadow: "0 0 30px rgba(0,0,0,0.8)",
  },
  closeModalBtn: {
    backgroundColor: "#ef4444",
    color: "#ffffff",
    border: "none",
    padding: "8px 20px",
    borderRadius: "6px",
    fontWeight: "700",
    cursor: "pointer",
  },
  loadingWrapper: {
    textAlign: "center",
    padding: "100px 0",
  },
  spinner: {
    width: "40px",
    height: "40px",
    border: "4px solid rgba(255,255,255,0.1)",
    borderTop: "4px solid #7c3aed",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
    margin: "0 auto 16px auto",
  },
  loadingText: {
    color: "#94a3b8",
  },
  errorCard: {
    maxWidth: "500px",
    margin: "100px auto",
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    padding: "30px",
    borderRadius: "14px",
    textAlign: "center",
  },
};

export default TradeDetail;
