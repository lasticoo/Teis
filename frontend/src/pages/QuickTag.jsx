import React, { useState, useEffect } from "react";
import MarketContextCard from "../components/MarketContextCard";

const QuickTag = () => {
  const [trades, setTrades] = useState([]);
  const [taxonomy, setTaxonomy] = useState([]);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Form states
  const [selectedSetups, setSelectedSetups] = useState([]);
  const [bias, setBias] = useState("bull_trend");
  const [session, setSession] = useState("asia");
  const [orderType, setOrderType] = useState("limit");
  const [confidence, setConfidence] = useState(5);
  const [psychology, setPsychology] = useState([]);
  const [planAdherence, setPlanAdherence] = useState(true);
  const [freeNotes, setFreeNotes] = useState("");
  const [screenshot, setScreenshot] = useState(null);
  const [screenshotPreview, setScreenshotPreview] = useState(null);

  // Countdown state
  const [countdown, setCountdown] = useState(null);

  const token = localStorage.getItem("token");

  // Fetch pending trades and taxonomy
  const fetchPendingData = async () => {
    try {
      setLoading(true);
      const res = await fetch("http://localhost:8000/api/v1/journal/pending", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error("Gagal mengambil data jurnal pending.");
      }

      const data = await res.json();
      setTrades(data.trades);
      setTaxonomy(data.taxonomy);

      // Default select the first untagged trade if none selected
      if (data.trades.length > 0 && !selectedTrade) {
        handleSelectTrade(data.trades[0]);
      } else if (selectedTrade) {
        // Refresh selected trade data
        const updated = data.trades.find((t) => t.id === selectedTrade.id);
        if (updated) {
          setSelectedTrade(updated);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPendingData();
  }, []);

  // Offline syncing
  useEffect(() => {
    const handleOnline = () => {
      syncOfflineTags();
    };
    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, []);

  // Timer countdown
  useEffect(() => {
    let timer;
    if (countdown !== null && countdown > 0) {
      timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            // Refresh DB state to check if locked
            fetchPendingData();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [countdown]);

  const detectSession = (timeString) => {
    const date = new Date(timeString);
    const utcHours = date.getUTCHours();
    if (utcHours >= 0 && utcHours < 8) return "asia";
    if (utcHours >= 8 && utcHours < 16) return "london";
    return "new_york";
  };

  const handleSelectTrade = (trade) => {
    setSelectedTrade(trade);
    setError("");
    setSuccessMsg("");
    setScreenshot(null);
    setScreenshotPreview(null);

    if (trade.is_tagged && trade.psychology) {
      setSelectedSetups(trade.setups || []);
      setConfidence(trade.psychology.confidence_level);
      setPsychology(trade.psychology.psychological_tags || []);
      setPlanAdherence(trade.psychology.plan_adherence);
      setFreeNotes(trade.psychology.free_notes || "");
      setOrderType(trade.order_type || "limit");
      setCountdown(trade.seconds_left !== null ? Math.floor(trade.seconds_left) : null);
    } else {
      // Fresh tag defaults
      setSelectedSetups([]);
      setBias("bull_trend");
      setSession(detectSession(trade.entry_time));
      setOrderType("limit");
      setConfidence(5);
      setPsychology([]);
      setPlanAdherence(true);
      setFreeNotes("");
      setCountdown(null);
    }
  };

  const handleSetupToggle = (id) => {
    if (selectedTrade?.is_tagged && countdown === 0) return; // Locked

    if (selectedSetups.includes(id)) {
      setSelectedSetups(selectedSetups.filter((item) => item !== id));
    } else {
      setSelectedSetups([...selectedSetups, id]);
    }
  };

  const handlePsychologyToggle = (tag) => {
    if (selectedTrade?.is_tagged && countdown === 0) return; // Locked

    if (psychology.includes(tag)) {
      setPsychology(psychology.filter((item) => item !== tag));
    } else {
      setPsychology([...psychology, tag]);
    }
  };

  const handleFileChange = (e) => {
    if (selectedTrade?.is_tagged && countdown === 0) return; // Locked

    const file = e.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError("Ukuran file tidak boleh lebih dari 5MB.");
        return;
      }
      setScreenshot(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setScreenshotPreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const syncOfflineTags = async () => {
    const offlineData = localStorage.getItem("teis_offline_tags");
    if (!offlineData) return;

    try {
      const payloads = JSON.parse(offlineData);
      for (const payload of payloads) {
        const formData = new FormData();
        Object.keys(payload).forEach((key) => {
          if (key === "setup" || key === "psychological_tags") {
            formData.append(key, JSON.stringify(payload[key]));
          } else {
            formData.append(key, payload[key]);
          }
        });

        await fetch("http://localhost:8000/api/v1/journal/tag", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });
      }
      localStorage.removeItem("teis_offline_tags");
      setSuccessMsg("Sinkronisasi offline berhasil diterapkan!");
      fetchPendingData();
    } catch (err) {
      console.error("Failed to sync offline tags", err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTrade) return;

    setError("");
    setSuccessMsg("");

    const payload = {
      trade_id: selectedTrade.id,
      setup: JSON.stringify(selectedSetups),
      bias_arah_manual: bias,
      session: session,
      confidence_level: confidence,
      psychological_tags: JSON.stringify(psychology),
      plan_adherence: planAdherence,
      free_notes: freeNotes,
      order_type: orderType,
    };

    // If offline, save to localStorage
    if (!navigator.onLine) {
      const existing = localStorage.getItem("teis_offline_tags");
      const list = existing ? JSON.parse(existing) : [];
      list.push(payload);
      localStorage.setItem("teis_offline_tags", JSON.stringify(list));
      setSuccessMsg("Koneksi terputus! Data disimpan secara lokal di browser dan akan disinkronkan saat online.");
      return;
    }

    const formData = new FormData();
    Object.keys(payload).forEach((key) => {
      formData.append(key, payload[key]);
    });

    if (screenshot) {
      formData.append("screenshot_before_entry", screenshot);
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/journal/tag", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        if (res.status === 409) {
          throw new Error("Gagal menyimpan: Jurnal trade ini sudah terkunci permanen.");
        }
        const data = await res.json();
        throw new Error(data.detail || "Terjadi kesalahan saat menyimpan tag.");
      }

      setSuccessMsg("Jurnal berhasil disimpan! Trade berada di window koreksi 120 detik.");
      setCountdown(120);
      fetchPendingData();
    } catch (err) {
      setError(err.message);
    }
  };

  const psychologyOptions = ["Sesuai Plan", "FOMO", "Revenge", "Lelah", "Tenang"];

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <div style={styles.header}>
          <h1 style={styles.title}>Jurnal Tangkap Cepat (Quick-Tag)</h1>
          <p style={styles.subtitle}>
            Isi data subjektif psikologis dan setup Anda segera setelah entry untuk menghindari hindsight bias.
          </p>
        </div>

        {/* Layout Column */}
        <div style={styles.layout}>
          {/* Sidebar Pending list */}
          <div style={styles.sidebar}>
            <h2 style={styles.sectionTitle}>Trade Menunggu Tag</h2>
            {trades.length === 0 ? (
              <div style={styles.emptyState}>Semua trade sudah ter-jurnal 🎉</div>
            ) : (
              <div style={styles.tradeList}>
                {trades.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => handleSelectTrade(t)}
                    style={{
                      ...styles.tradeItem,
                      ...(selectedTrade?.id === t.id ? styles.tradeItemActive : {}),
                    }}
                  >
                    <div style={styles.tradeItemHeader}>
                      <span style={styles.pair}>{t.pair}</span>
                      <span
                        style={
                          t.direction === "long" ? styles.dirLong : styles.dirShort
                        }
                      >
                        {t.direction.toUpperCase()}
                      </span>
                    </div>
                    <div style={styles.tradeItemDetails}>
                      <span>Harga: {t.entry_price}</span>
                      <span>
                        {t.is_locked
                          ? "🔒 Terkunci Permanen"
                          : t.is_tagged
                          ? "🟡 Terisi (Dalam Koreksi)"
                          : "🔴 Belum Diisi"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Main Form container */}
          {selectedTrade && (
            <div style={styles.formContainer}>
              <div style={styles.formHeader}>
                <div style={styles.formHeaderInfo}>
                  <h2 style={styles.formTitle}>
                    Detail Posisi: {selectedTrade.pair} ({selectedTrade.direction.toUpperCase()})
                  </h2>
                  <span style={styles.entryTime}>
                    Masuk pada: {new Date(selectedTrade.entry_time).toLocaleString()}
                  </span>
                </div>

                {/* Progress bar window koreksi */}
                {countdown !== null && (
                  <div style={styles.countdownWrapper}>
                    <div style={styles.countdownHeader}>
                      <span>Sisa Waktu Koreksi: {countdown} detik</span>
                      <span>{countdown > 0 ? "⚠️ Window Koreksi Aktif" : "🔒 Terkunci Permanen"}</span>
                    </div>
                    <div style={styles.progressContainer}>
                      <div
                        style={{
                          ...styles.progressBar,
                          width: `${(countdown / 120) * 100}%`,
                          backgroundColor: countdown > 20 ? "#10b981" : "#ef4444",
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {error && <div style={styles.error}>{error}</div>}
              {successMsg && <div style={styles.success}>{successMsg}</div>}

              <form onSubmit={handleSubmit} style={styles.form}>
                {/* Row Setup */}
                <div style={styles.inputGroup}>
                  <label style={styles.label}>1. Pilihlah Setup Trade (Multi-select)</label>
                  <div style={styles.pillsRow}>
                    {taxonomy.map((tax) => (
                      <button
                        type="button"
                        key={tax.id}
                        disabled={selectedTrade.is_tagged && countdown === 0}
                        onClick={() => handleSetupToggle(tax.id)}
                        style={{
                          ...styles.pillButton,
                          ...(selectedSetups.includes(tax.id)
                            ? styles.pillButtonActive
                            : {}),
                        }}
                      >
                        {tax.tag_name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Grid Inputs */}
                <div style={styles.grid}>
                  <div style={styles.inputGroup}>
                    <label style={styles.label}>2. Bias Arah</label>
                    <select
                      value={bias}
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={(e) => setBias(e.target.value)}
                      style={styles.select}
                    >
                      <option value="bull_trend">BULL (Up-Trend)</option>
                      <option value="bear_trend">BEAR (Down-Trend)</option>
                      <option value="range">RANGE (Consolidation)</option>
                    </select>
                  </div>

                  <div style={styles.inputGroup}>
                    <label style={styles.label}>3. Sesi Trading</label>
                    <select
                      value={session}
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={(e) => setSession(e.target.value)}
                      style={styles.select}
                    >
                      <option value="asia">ASIA Session</option>
                      <option value="london">LONDON Session</option>
                      <option value="new_york">NEW YORK Session</option>
                    </select>
                  </div>

                  <div style={styles.inputGroup}>
                    <label style={styles.label}>4. Tipe Order</label>
                    <select
                      value={orderType}
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={(e) => setOrderType(e.target.value)}
                      style={styles.select}
                    >
                      <option value="limit">Limit Order</option>
                      <option value="market">Market Order</option>
                    </select>
                  </div>

                  <div style={styles.inputGroup}>
                    <label style={styles.label}>
                      5. Tingkat Keyakinan (Confidence: {confidence}/10)
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={confidence}
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={(e) => setConfidence(parseInt(e.target.value))}
                      style={styles.slider}
                    />
                  </div>
                </div>

                {/* Psychology Tag Pill Buttons */}
                <div style={styles.inputGroup}>
                  <label style={styles.label}>6. Kondisi Emosional Saat Entry (Multi-select)</label>
                  <div style={styles.pillsRow}>
                    {psychologyOptions.map((tag) => (
                      <button
                        type="button"
                        key={tag}
                        disabled={selectedTrade.is_tagged && countdown === 0}
                        onClick={() => handlePsychologyToggle(tag)}
                        style={{
                          ...styles.pillButton,
                          ...(psychology.includes(tag) ? styles.pillButtonActive : {}),
                        }}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Plan Adherence Toggle */}
                <div style={styles.inputGroup}>
                  <div style={styles.toggleRow}>
                    <label style={styles.label}>7. Apakah Entry Sesuai Trading Plan?</label>
                    <button
                      type="button"
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onClick={() => setPlanAdherence(!planAdherence)}
                      style={{
                        ...styles.toggleButton,
                        ...(planAdherence ? styles.toggleButtonActive : {}),
                      }}
                    >
                      {planAdherence ? "YA (Patuh Plan)" : "TIDAK (Impulsif)"}
                    </button>
                  </div>
                </div>

                {/* Screenshot & Notes */}
                <div style={styles.grid}>
                  <div style={styles.inputGroup}>
                    <label style={styles.label}>8. Upload Screenshot Chart Sebelum Entry</label>
                    <input
                      type="file"
                      accept="image/*"
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={handleFileChange}
                      style={styles.fileInput}
                    />
                    {screenshotPreview && (
                      <div style={styles.previewContainer}>
                        <img
                          src={screenshotPreview}
                          alt="Screenshot Preview"
                          style={styles.previewImage}
                        />
                      </div>
                    )}
                    {!screenshotPreview && selectedTrade.screenshot_url && (
                      <div style={styles.previewContainer}>
                        <img
                          src={selectedTrade.screenshot_url}
                          alt="Screenshot Database"
                          style={styles.previewImage}
                        />
                      </div>
                    )}
                  </div>

                  <div style={styles.inputGroup}>
                    <label style={styles.label}>9. Catatan Bebas Pendek</label>
                    <textarea
                      value={freeNotes}
                      disabled={selectedTrade.is_tagged && countdown === 0}
                      onChange={(e) => setFreeNotes(e.target.value)}
                      placeholder="Masukkan detail tambahan tentang entry Anda..."
                      style={styles.textarea}
                    />
                  </div>
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={selectedTrade.is_tagged && countdown === 0}
                  style={{
                    ...styles.submitButton,
                    ...((selectedTrade.is_tagged && countdown === 0)
                      ? styles.submitButtonDisabled
                      : {}),
                  }}
                >
                  {selectedTrade.is_tagged
                    ? countdown > 0
                      ? "Perbarui Jurnal (Edit)"
                      : "Jurnal Terkunci"
                    : "Simpan & Tag Jurnal"}
                </button>
              </form>

              {/* ── Market Context Card — tampil jika sudah pernah di-tag ── */}
              {selectedTrade.is_tagged && (
                <div style={{ marginTop: 24 }}>
                  <MarketContextCard tradeId={selectedTrade.id} />
                </div>
              )}
            </div>
          )}
        </div>
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
    maxWidth: "1200px",
    margin: "0 auto",
  },
  header: {
    marginBottom: "35px",
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
  layout: {
    display: "flex",
    gap: "30px",
    flexWrap: "wrap",
  },
  sidebar: {
    flex: "1 1 300px",
    backgroundColor: "rgba(22, 19, 39, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: "12px",
    padding: "20px",
    maxHeight: "650px",
    overflowY: "auto",
  },
  sectionTitle: {
    fontSize: "16px",
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: "20px",
  },
  emptyState: {
    textAlign: "center",
    color: "#64748b",
    padding: "40px 0",
    fontSize: "14px",
  },
  tradeList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  tradeItem: {
    backgroundColor: "rgba(255, 255, 255, 0.02)",
    border: "1px solid rgba(255, 255, 255, 0.04)",
    borderRadius: "8px",
    padding: "14px",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  tradeItemActive: {
    backgroundColor: "rgba(124, 58, 237, 0.15)",
    border: "1px solid #7c3aed",
    boxShadow: "0 0 10px rgba(124, 58, 237, 0.2)",
  },
  tradeItemHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "6px",
  },
  pair: {
    fontWeight: "700",
    color: "#ffffff",
    fontSize: "15px",
  },
  dirLong: {
    color: "#10b981",
    fontSize: "12px",
    fontWeight: "700",
  },
  dirShort: {
    color: "#ef4444",
    fontSize: "12px",
    fontWeight: "700",
  },
  tradeItemDetails: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#94a3b8",
  },
  formContainer: {
    flex: "2 1 600px",
    backgroundColor: "rgba(22, 19, 39, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    borderRadius: "12px",
    padding: "30px",
  },
  formHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    flexWrap: "wrap",
    gap: "20px",
    marginBottom: "25px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
    paddingBottom: "20px",
  },
  formHeaderInfo: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  formTitle: {
    fontSize: "18px",
    fontWeight: "700",
    color: "#ffffff",
    margin: 0,
  },
  entryTime: {
    fontSize: "12px",
    color: "#64748b",
  },
  countdownWrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    width: "220px",
  },
  countdownHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "11px",
    fontWeight: "600",
    color: "#94a3b8",
  },
  progressContainer: {
    height: "6px",
    width: "100%",
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    borderRadius: "3px",
    overflow: "hidden",
  },
  progressBar: {
    height: "100%",
    borderRadius: "3px",
    transition: "width 1s linear, background-color 0.5s ease",
  },
  error: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "8px",
    color: "#f87171",
    padding: "12px",
    fontSize: "13px",
    marginBottom: "20px",
  },
  success: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    borderRadius: "8px",
    color: "#34d399",
    padding: "12px",
    fontSize: "13px",
    marginBottom: "20px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  label: {
    fontSize: "13px",
    fontWeight: "600",
    color: "#94a3b8",
  },
  pillsRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px",
  },
  pillButton: {
    backgroundColor: "rgba(255, 255, 255, 0.03)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    color: "#cbd5e1",
    padding: "10px 16px",
    borderRadius: "20px",
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  pillButtonActive: {
    backgroundColor: "rgba(124, 58, 237, 0.2)",
    border: "1px solid #7c3aed",
    color: "#ffffff",
    boxShadow: "0 0 8px rgba(124, 58, 237, 0.2)",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "20px",
  },
  select: {
    backgroundColor: "rgba(15, 12, 30, 0.8)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    color: "#ffffff",
    padding: "12px",
    borderRadius: "8px",
    fontSize: "13px",
    cursor: "pointer",
    outline: "none",
  },
  slider: {
    width: "100%",
    cursor: "pointer",
    height: "6px",
    borderRadius: "3px",
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    outline: "none",
    accentColor: "#7c3aed",
  },
  toggleRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "rgba(255, 255, 255, 0.01)",
    border: "1px solid rgba(255, 255, 255, 0.03)",
    padding: "14px 20px",
    borderRadius: "8px",
  },
  toggleButton: {
    backgroundColor: "#ef4444",
    border: "none",
    color: "#ffffff",
    padding: "8px 16px",
    borderRadius: "6px",
    fontWeight: "700",
    fontSize: "12px",
    cursor: "pointer",
    transition: "background-color 0.2s ease",
  },
  toggleButtonActive: {
    backgroundColor: "#10b981",
  },
  fileInput: {
    color: "#94a3b8",
    fontSize: "13px",
  },
  previewContainer: {
    marginTop: "10px",
    borderRadius: "8px",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    overflow: "hidden",
    maxWidth: "300px",
    maxHeight: "200px",
  },
  previewImage: {
    width: "100%",
    height: "auto",
    display: "block",
  },
  textarea: {
    backgroundColor: "rgba(15, 12, 30, 0.8)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    color: "#ffffff",
    padding: "12px",
    borderRadius: "8px",
    fontSize: "13px",
    minHeight: "100px",
    resize: "vertical",
    outline: "none",
  },
  submitButton: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "14px",
    fontSize: "14px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "all 0.2s ease",
    boxShadow: "0 4px 15px rgba(124, 58, 237, 0.3)",
    alignSelf: "flex-start",
    paddingLeft: "30px",
    paddingRight: "30px",
  },
  submitButtonDisabled: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    color: "#64748b",
    cursor: "not-allowed",
    boxShadow: "none",
  },
};

export default QuickTag;
