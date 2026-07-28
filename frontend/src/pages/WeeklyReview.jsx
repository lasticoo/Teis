import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";

const WeeklyReview = () => {
  const [journalData, setJournalData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState("binance_sync"); // Default to Live Trade ('binance_sync')
  const [selectedWeekIndex, setSelectedWeekIndex] = useState(0); // 0 = Current Week, 1 = Previous Week, etc.
  const [zoomedImage, setZoomedImage] = useState(null);
  const [weeklyNotes, setWeeklyNotes] = useState("");
  const [savedMsg, setSavedMsg] = useState("");

  const token = localStorage.getItem("token") || localStorage.getItem("access_token");

  const fetchJournalForReview = async () => {
    setLoading(true);
    try {
      let url = `http://localhost:8000/api/v1/journal/list?data_source=${dataSource}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setJournalData(data.trades || []);
      }
    } catch (err) {
      console.error("Gagal mengambil data review mingguan:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJournalForReview();
  }, [dataSource]);

  useEffect(() => {
    const saved = localStorage.getItem(`teis_weekly_reflection_${selectedWeekIndex}`);
    setWeeklyNotes(saved || "");
  }, [selectedWeekIndex]);

  const handleSaveNotes = () => {
    localStorage.setItem(`teis_weekly_reflection_${selectedWeekIndex}`, weeklyNotes);
    setSavedMsg("✅ Catatan refleksi minggu ini berhasil disimpan!");
    setTimeout(() => setSavedMsg(""), 3000);
  };

  // Helper to calculate start & end date for week offset
  const getWeekRange = (weekOffset) => {
    const now = new Date();
    const currentDay = now.getDay();
    const diffToMonday = now.getDate() - currentDay + (currentDay === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diffToMonday - weekOffset * 7));
    monday.setHours(0, 0, 0, 0);

    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    sunday.setHours(23, 59, 59, 999);

    return { monday, sunday };
  };

  // Filter trades by selected week range
  const { monday, sunday } = getWeekRange(selectedWeekIndex);
  
  const tradesForSelectedWeek = journalData.filter((t) => {
    if (!t.entry_time) return false;
    const entryDt = new Date(t.entry_time);
    return entryDt >= monday && entryDt <= sunday;
  });

  const formatDateLabel = (d) => {
    return d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
  };

  const weekLabel = selectedWeekIndex === 0 
    ? `Minggu Ini (${formatDateLabel(monday)} - ${formatDateLabel(sunday)})`
    : `Minggu Ke-${selectedWeekIndex + 1} Lalu (${formatDateLabel(monday)} - ${formatDateLabel(sunday)})`;

  // Calculate metrics for selected week
  const totalTrades = tradesForSelectedWeek.length;
  const wins = tradesForSelectedWeek.filter(t => (t.pnl || 0) > 0).length;
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : "0.0";
  const totalPnl = tradesForSelectedWeek.reduce((acc, t) => acc + (t.pnl || 0), 0);
  const totalR = tradesToDisplay => tradesToDisplay.reduce((acc, t) => acc + (t.rr_realized || 0), 0);
  const totalRVal = totalR(tradesForSelectedWeek);

  const [aiWeeklyLoading, setAiWeeklyLoading] = useState(false);
  const [aiWeeklyReview, setAiWeeklyReview] = useState(null);

  const fetchAiWeeklyReview = async () => {
    setAiWeeklyLoading(true);
    try {
      const formattedStart = monday.toISOString().split("T")[0];
      const formattedEnd = sunday.toISOString().split("T")[0];
      const res = await fetch("http://localhost:8000/api/v1/ai-coach/weekly-review", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          start_date: formattedStart,
          end_date: formattedEnd,
          data_source: dataSource
        })
      });
      if (res.ok) {
        const data = await res.json();
        setAiWeeklyReview(data.review_markdown);
      }
    } catch (err) {
      console.error("Gagal mendapatkan evaluasi AI Coach Mingguan:", err);
    } finally {
      setAiWeeklyLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Header Bar */}
        <div style={styles.headerRow}>
          <div>
            <h1 style={styles.title}>Galeri & Review Mingguan Trader</h1>
            <span style={styles.subtitle}>
              Evaluasi kualitatif mingguan, dokumentasi visual chart 4H/1H, dan refleksi psikologi
            </span>
          </div>

          {/* Filter Source Toggle */}
          <div style={styles.filterSourceGroup}>
            <button
              onClick={() => setDataSource("all")}
              style={{
                ...styles.sourceBtn,
                ...(dataSource === "all" ? styles.sourceBtnActive : {})
              }}
            >
              📊 Semua Trade
            </button>
            <button
              onClick={() => setDataSource("binance_sync")}
              style={{
                ...styles.sourceBtn,
                ...(dataSource === "binance_sync" ? styles.sourceBtnActive : {})
              }}
            >
              🟢 Live/Sync Saja
            </button>
            <button
              onClick={() => setDataSource("historical_import")}
              style={{
                ...styles.sourceBtn,
                ...(dataSource === "historical_import" ? styles.sourceBtnActive : {})
              }}
            >
              📥 Import Saja
            </button>
          </div>
        </div>

        {/* Week Selector Bar */}
        <div style={styles.weekNavBar}>
          <button
            onClick={() => {
              setSelectedWeekIndex(selectedWeekIndex + 1);
              setAiWeeklyReview(null);
            }}
            style={styles.weekNavBtn}
          >
            ← Minggu Sebelumnya
          </button>
          <div style={styles.weekDisplayBox}>
            <span style={{ fontSize: "14px", fontWeight: "800", color: "#a78bfa" }}>📅 {weekLabel}</span>
          </div>
          <button
            onClick={() => {
              setSelectedWeekIndex(Math.max(0, selectedWeekIndex - 1));
              setAiWeeklyReview(null);
            }}
            disabled={selectedWeekIndex === 0}
            style={{
              ...styles.weekNavBtn,
              opacity: selectedWeekIndex === 0 ? 0.4 : 1,
              cursor: selectedWeekIndex === 0 ? "not-allowed" : "pointer"
            }}
          >
            Minggu Berikutnya →
          </button>
        </div>

        {/* Weekly Metric Cards */}
        <div style={styles.metricGrid}>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>TOTAL TRADE MINGGU INI</span>
            <span style={styles.metricVal}>{totalTrades} Transaksi</span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>WIN RATE MINGGUAN</span>
            <span style={{ ...styles.metricVal, color: Number(winRate) >= 50 ? "#22c55e" : "#fbbf24" }}>
              {winRate}%
            </span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>AKUMULASI RR (R)</span>
            <span style={{ ...styles.metricVal, color: totalRVal >= 0 ? "#22c55e" : "#ef4444" }}>
              {totalRVal >= 0 ? `+${totalRVal.toFixed(2)} R` : `${totalRVal.toFixed(2)} R`}
            </span>
          </div>
          <div style={styles.metricCard}>
            <span style={styles.metricLabel}>NET PnL ($)</span>
            <span style={{ ...styles.metricVal, color: totalPnl >= 0 ? "#22c55e" : "#ef4444" }}>
              {totalPnl >= 0 ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`}
            </span>
          </div>
        </div>

        {/* Section 0: AI Coach Weekly Evaluation Card */}
        <div style={{
          backgroundColor: "#13192b",
          border: "1px solid rgba(139, 92, 246, 0.4)",
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 8px 32px rgba(139, 92, 246, 0.15)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "18px", fontWeight: "800", background: "linear-gradient(90deg, #a78bfa, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                🤖 AI Coach Evaluation & Strategic Mindset Mingguan
              </h3>
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>
                Analisis AI terhadap performa R-Multiple, kedisiplinan emosional, dan 3 instruksi fokus minggu depan
              </span>
            </div>
            <button
              onClick={fetchAiWeeklyReview}
              disabled={aiWeeklyLoading}
              style={{
                backgroundColor: aiWeeklyLoading ? "#4c1d95" : "#7c3aed",
                color: "#ffffff",
                border: "none",
                borderRadius: "10px",
                padding: "10px 20px",
                fontWeight: "700",
                fontSize: "13px",
                cursor: aiWeeklyLoading ? "not-allowed" : "pointer",
                boxShadow: "0 4px 15px rgba(124, 58, 237, 0.4)",
                transition: "all 0.2s ease"
              }}
            >
              {aiWeeklyLoading ? "⏳ Menganalisis Mingguan..." : "⚡ Hasilkan Evaluasi AI Coach Minggu Ini"}
            </button>
          </div>

          {aiWeeklyReview ? (
            <div style={{
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              borderRadius: "12px",
              padding: "20px",
              fontSize: "14px",
              lineHeight: "1.7",
              color: "#cbd5e1",
              whiteSpace: "pre-wrap"
            }}>
              {aiWeeklyReview}
            </div>
          ) : (
            <div style={{
              backgroundColor: "rgba(15, 23, 42, 0.5)",
              border: "1px dashed rgba(139, 92, 246, 0.3)",
              borderRadius: "12px",
              padding: "20px",
              textAlign: "center",
              color: "#94a3b8",
              fontSize: "13px"
            }}>
              💡 Klik tombol <b>"⚡ Hasilkan Evaluasi AI Coach Minggu Ini"</b> di atas untuk mendapatkan analisis kuantitatif dan rekomendasi kualitatif AI untuk transaksi minggu ini.
            </div>
          )}
        </div>

        {/* Section 1: Chart Screenshot Gallery */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>📸 Galeri Tangkapan Layar Chart ({tradesForSelectedWeek.length} Trade)</h3>
            <span style={styles.sectionSubtitle}>Dokumentasi visual struktur chart 4H & 1H sebelum dan sesudah exit</span>
          </div>

          {loading ? (
            <div style={styles.loadingBox}>Memuat dokumentasi screenshot chart...</div>
          ) : tradesForSelectedWeek.length === 0 ? (
            <div style={styles.emptyBox}>
              Tidak ada transaksi tercatat untuk <b>{weekLabel}</b> (Filter: {dataSource === "all" ? "Semua Data" : dataSource}).
            </div>
          ) : (
            <div style={styles.galleryGrid}>
              {tradesForSelectedWeek.map((t) => {
                const screenshots = t.screenshots || [];
                return (
                  <div key={t.id} style={styles.tradeCard}>
                    <div style={styles.tradeHeader}>
                      <div>
                        <span style={styles.pairTitle}>{t.pair}</span>
                        <span style={{ ...styles.badgeSide, color: t.direction?.toUpperCase() === "LONG" ? "#22c55e" : "#ef4444" }}>
                          {t.direction?.toUpperCase()}
                        </span>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span style={styles.sourceBadge}>{t.source_badge || t.data_source}</span>
                        <span style={{ ...styles.pnlTag, color: (t.pnl || 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                          {(t.pnl || 0) >= 0 ? `+$${(t.pnl || 0).toFixed(2)}` : `-$${Math.abs(t.pnl || 0).toFixed(2)}`}
                        </span>
                      </div>
                    </div>

                    {/* Screenshot Images */}
                    <div style={styles.imgGrid}>
                      {screenshots.length === 0 ? (
                        <div style={styles.noImgBox}>Tidak ada foto chart diunggah</div>
                      ) : (
                        screenshots.map((s, idx) => (
                          <div key={idx} style={styles.imgWrapper} onClick={() => setZoomedImage(s.url)}>
                            <img src={s.url} alt={s.stage} style={styles.thumbImg} />
                            <span style={styles.imgStageTag}>
                              {s.stage === "before_entry_4h" ? "Chart 4H" : s.stage === "before_entry_1h" ? "Chart 1H" : "Exit Chart"}
                            </span>
                          </div>
                        ))
                      )}
                    </div>

                    <div style={styles.tradeFooter}>
                      <span style={styles.setupText}>🏷️ {t.setups?.join(", ") || "Order Block"}</span>
                      <Link to={`/journal/detail/${t.id}`} style={styles.linkDetail}>
                        Detail Trade →
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 2: Qualitative Weekly Reflection Journal */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h3 style={styles.sectionTitle}>✍️ Jurnal Refleksi & Catatan Bebas ({weekLabel})</h3>
            <span style={styles.sectionSubtitle}>
              Evaluasi emosi, kesalahan eksekusi, dan fokus perbaikan untuk minggu depan
            </span>
          </div>

          {savedMsg && <div style={styles.successBanner}>{savedMsg}</div>}

          <textarea
            value={weeklyNotes}
            onChange={(e) => setWeeklyNotes(e.target.value)}
            placeholder="Tuliskan refleksi minggu ini: Apakah ada emosi FOMO? Apakah batas risiko selalu dipatuhi? Apa fokus utama minggu depan..."
            style={styles.textareaNotes}
            rows={5}
          />

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "12px" }}>
            <button onClick={handleSaveNotes} style={styles.btnSave}>
              💾 Simpan Refleksi Minggu Ini
            </button>
          </div>
        </div>
      </div>

      {/* Zoom Modal */}
      {zoomedImage && (
        <div style={styles.modalOverlay} onClick={() => setZoomedImage(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <img src={zoomedImage} alt="Zoomed Chart" style={styles.fullImg} />
            <button onClick={() => setZoomedImage(null)} style={styles.closeBtn}>✕ Tutup</button>
          </div>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0b0e11",
    color: "#e2e8f0",
    padding: "0"
  },
  content: {
    maxWidth: "1200px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "20px"
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "16px"
  },
  badgePill: {
    display: "inline-block",
    backgroundColor: "rgba(167, 139, 250, 0.15)",
    border: "1px solid rgba(167, 139, 250, 0.3)",
    color: "#a78bfa",
    fontSize: "11px",
    fontWeight: "700",
    padding: "2px 10px",
    borderRadius: "12px",
    marginBottom: "4px"
  },
  title: {
    margin: 0,
    fontSize: "24px",
    fontWeight: "800",
    color: "#ffffff"
  },
  subtitle: {
    fontSize: "13px",
    color: "#64748b"
  },
  filterSourceGroup: {
    display: "flex",
    gap: "6px",
    backgroundColor: "#13161f",
    padding: "4px",
    borderRadius: "10px",
    border: "1px solid #1e2329"
  },
  sourceBtn: {
    backgroundColor: "transparent",
    border: "none",
    color: "#94a3b8",
    padding: "8px 14px",
    borderRadius: "8px",
    fontSize: "12.5px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.2s"
  },
  sourceBtnActive: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    fontWeight: "700"
  },
  weekNavBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "12px",
    padding: "10px 16px"
  },
  weekNavBtn: {
    backgroundColor: "#1e293b",
    color: "#e2e8f0",
    border: "none",
    borderRadius: "8px",
    padding: "8px 16px",
    fontSize: "12.5px",
    fontWeight: "700",
    cursor: "pointer"
  },
  weekDisplayBox: {
    textAlign: "center"
  },
  metricGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "14px"
  },
  metricCard: {
    backgroundColor: "#13161f",
    border: "1px solid #1e2329",
    borderRadius: "12px",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "6px"
  },
  metricLabel: {
    fontSize: "11px",
    color: "#64748b",
    fontWeight: "700"
  },
  metricVal: {
    fontSize: "20px",
    fontWeight: "800",
    color: "#f8fafc"
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
  galleryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "16px"
  },
  tradeCard: {
    backgroundColor: "#0b0e11",
    border: "1px solid #1e2329",
    borderRadius: "12px",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px"
  },
  tradeHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start"
  },
  pairTitle: {
    fontSize: "16px",
    fontWeight: "800",
    color: "#ffffff",
    marginRight: "8px"
  },
  badgeSide: {
    fontSize: "11px",
    fontWeight: "800"
  },
  sourceBadge: {
    display: "block",
    fontSize: "10.5px",
    color: "#94a3b8",
    fontWeight: "600"
  },
  pnlTag: {
    fontSize: "14px",
    fontWeight: "800"
  },
  imgGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))",
    gap: "8px",
    minHeight: "80px"
  },
  imgWrapper: {
    position: "relative",
    borderRadius: "8px",
    overflow: "hidden",
    cursor: "pointer",
    border: "1px solid #1e293b",
    height: "90px"
  },
  thumbImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover"
  },
  imgStageTag: {
    position: "absolute",
    bottom: "4px",
    left: "4px",
    backgroundColor: "rgba(11, 14, 17, 0.85)",
    color: "#cbd5e1",
    fontSize: "9.5px",
    fontWeight: "700",
    padding: "2px 6px",
    borderRadius: "4px"
  },
  noImgBox: {
    backgroundColor: "#13161f",
    border: "1px dashed #1e293b",
    borderRadius: "8px",
    padding: "20px",
    textAlign: "center",
    color: "#64748b",
    fontSize: "12px",
    width: "100%"
  },
  tradeFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: "12px"
  },
  setupText: {
    color: "#a78bfa",
    fontWeight: "600"
  },
  linkDetail: {
    color: "#38bdf8",
    textDecoration: "none",
    fontWeight: "600"
  },
  textareaNotes: {
    width: "100%",
    backgroundColor: "#0b0e11",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    color: "#f8fafc",
    padding: "14px",
    fontSize: "13.5px",
    outline: "none",
    resize: "vertical",
    boxSizing: "border-box"
  },
  btnSave: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: "10px",
    padding: "10px 20px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(124, 58, 237, 0.4)"
  },
  successBanner: {
    backgroundColor: "rgba(34, 197, 94, 0.15)",
    border: "1px solid #22c55e",
    color: "#22c55e",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    marginBottom: "12px"
  },
  loadingBox: {
    textAlign: "center",
    color: "#64748b",
    padding: "30px"
  },
  emptyBox: {
    textAlign: "center",
    color: "#64748b",
    padding: "30px"
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.85)",
    zIndex: 999,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "20px"
  },
  modalContent: {
    position: "relative",
    maxWidth: "90%",
    maxHeight: "90%",
    backgroundColor: "#13161f",
    borderRadius: "12px",
    overflow: "hidden",
    padding: "10px"
  },
  fullImg: {
    maxWidth: "100%",
    maxHeight: "80vh",
    objectFit: "contain",
    borderRadius: "8px"
  },
  closeBtn: {
    position: "absolute",
    top: "16px",
    right: "16px",
    backgroundColor: "rgba(246, 70, 93, 0.8)",
    color: "#ffffff",
    border: "none",
    borderRadius: "6px",
    padding: "6px 14px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer"
  }
};

export default WeeklyReview;
