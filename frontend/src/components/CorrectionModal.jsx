import React, { useState, useEffect } from "react";

const FIELD_OPTIONS = [
  { value: "screenshot_before_entry", label: "🖼️ Screenshot Chart Sebelum Entry (Before Entry)" },
  { value: "confidence_level", label: "Tingkat Keyakinan (Confidence Level 1-10)" },
  { value: "plan_adherence", label: "Kepatuhan pada Plan (Plan Adherence)" },
  { value: "psychological_tags", label: "Kondisi Emosional Saat Entry" },
  { value: "free_notes", label: "Catatan Bebas (Free Notes)" },
  { value: "order_type", label: "Tipe Order (Limit / Market)" },
  { value: "moved_to_breakeven", label: "Status Moved to Breakeven (BE)" },
  { value: "trailing_stop_used", label: "Status Trailing Stop Used" },
  { value: "exit_reason", label: "Alasan Exit Trade" },
  { value: "bias_arah_manual", label: "Bias Arah Trend Pasar" },
  { value: "session", label: "Sesi Trading (Asia/London/NY)" },
];

const CorrectionModal = ({ isOpen, onClose, trade, onSuccess }) => {
  const [fieldName, setFieldName] = useState("screenshot_before_entry");
  const [oldValue, setOldValue] = useState("");
  const [newValue, setNewValue] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const getInitialOldValue = (field, tradeObj) => {
    if (!tradeObj) return "—";
    switch (field) {
      case "screenshot_before_entry":
        const sc = tradeObj.screenshots?.find((s) => s.stage === "before_entry");
        return sc ? `screenshots/${tradeObj.id}/before_entry.webp` : "Belum Ada Screenshot";
      case "confidence_level":
        return tradeObj.psychology?.confidence_level !== undefined && tradeObj.psychology?.confidence_level !== null
          ? String(tradeObj.psychology.confidence_level)
          : "—";
      case "plan_adherence":
        return tradeObj.psychology?.plan_adherence !== undefined
          ? tradeObj.psychology.plan_adherence
            ? "YA"
            : "TIDAK"
          : "—";
      case "psychological_tags":
        return tradeObj.psychology?.psychological_tags && tradeObj.psychology.psychological_tags.length > 0
          ? tradeObj.psychology.psychological_tags.join(", ")
          : "—";
      case "free_notes":
        return tradeObj.psychology?.free_notes || "—";
      case "order_type":
        return tradeObj.execution?.order_type ? tradeObj.execution.order_type.toUpperCase() : "MARKET";
      case "moved_to_breakeven":
        return tradeObj.execution?.moved_to_breakeven ? "YA" : "TIDAK";
      case "trailing_stop_used":
        return tradeObj.execution?.trailing_stop_used ? "YA" : "TIDAK";
      case "exit_reason":
        return tradeObj.execution?.exit_reason || "—";
      case "bias_arah_manual":
        return tradeObj.market_context?.bias_arah_manual || "—";
      case "session":
        return tradeObj.market_context?.session || "—";
      default:
        return "—";
    }
  };

  const getInitialNewValue = (field) => {
    switch (field) {
      case "confidence_level":
        return "8";
      case "plan_adherence":
        return "YA";
      case "moved_to_breakeven":
        return "YA";
      case "trailing_stop_used":
        return "YA";
      case "order_type":
        return "limit";
      case "bias_arah_manual":
        return "bull_trend";
      case "session":
        return "asia";
      case "screenshot_before_entry":
        return "";
      default:
        return "";
    }
  };

  useEffect(() => {
    if (trade && fieldName) {
      const fetchedOld = getInitialOldValue(fieldName, trade);
      setOldValue(fetchedOld);
      setNewValue(getInitialNewValue(fieldName));
      setSelectedFile(null);
    }
  }, [fieldName, trade]);

  if (!isOpen || !trade) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");

    const cleanReason = reason.trim();
    if (cleanReason.length < 10) {
      setError("Alasan koreksi wajib diisi minimal 10 karakter.");
      return;
    }

    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    setLoading(true);

    try {
      // Specialized upload flow for screenshot_before_entry correction
      if (fieldName === "screenshot_before_entry") {
        if (!selectedFile) {
          setError("Silakan pilih file gambar baru untuk koreksi screenshot Sebelum Entry.");
          setLoading(false);
          return;
        }

        const formData = new FormData();
        formData.append("trade_id", trade.id);
        formData.append("stage", "before_entry");
        formData.append("file", selectedFile);
        formData.append("is_correction", "true");
        formData.append("reason", cleanReason);

        const res = await fetch("http://localhost:8000/api/v1/screenshots/upload", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Gagal mengunggah koreksi screenshot.");
        }

        setSuccessMsg("✅ Koreksi screenshot Sebelum Entry berhasil dikompresi (WebP 80%) & dicatat di Audit Log!");
        setTimeout(() => {
          if (onSuccess) onSuccess();
          onClose();
        }, 1200);
        return;
      }

      // Standard field correction flow
      if (!newValue.trim()) {
        setError("Nilai baru wajib diisi.");
        setLoading(false);
        return;
      }

      const res = await fetch("http://localhost:8000/api/v1/journal/correct", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          original_trade_id: trade.id,
          field_name: fieldName,
          old_value: oldValue || null,
          new_value: newValue.trim(),
          reason: cleanReason,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gagal mengajukan koreksi.");
      }

      setSuccessMsg("✅ Koreksi data trade berhasil dicatat dan diterapkan pada data aktif.");
      setTimeout(() => {
        if (onSuccess) onSuccess();
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const reasonLen = reason.trim().length;

  const renderNewValueInput = () => {
    switch (fieldName) {
      case "screenshot_before_entry":
        return (
          <div style={styles.filePickerBox}>
            <label style={styles.filePickerLabel}>
              📁 Upload Gambar Baru (PNG, JPG, WEBP - Max 5MB)
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                    setNewValue(e.target.files[0].name);
                  }
                }}
                style={{ display: "none" }}
              />
            </label>
            {selectedFile ? (
              <div style={styles.selectedFilePill}>
                📷 Terpilih: <b>{selectedFile.name}</b> ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
              </div>
            ) : (
              <span style={styles.filePickerHint}>Klik untuk memilih file chart pengganti</span>
            )}
          </div>
        );
      case "confidence_level":
        return (
          <select value={newValue} onChange={(e) => setNewValue(e.target.value)} style={styles.select}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
              <option key={num} value={String(num)}>
                {num} / 10
              </option>
            ))}
          </select>
        );
      case "plan_adherence":
      case "moved_to_breakeven":
      case "trailing_stop_used":
        return (
          <select value={newValue} onChange={(e) => setNewValue(e.target.value)} style={styles.select}>
            <option value="YA">YA (Ya/Patuh)</option>
            <option value="TIDAK">TIDAK (Tidak/Impulsif)</option>
          </select>
        );
      case "order_type":
        return (
          <select value={newValue} onChange={(e) => setNewValue(e.target.value)} style={styles.select}>
            <option value="limit">Limit Order</option>
            <option value="market">Market Order</option>
          </select>
        );
      case "bias_arah_manual":
        return (
          <select value={newValue} onChange={(e) => setNewValue(e.target.value)} style={styles.select}>
            <option value="bull_trend">Bullish Trend 📈</option>
            <option value="bear_trend">Bearish Trend 📉</option>
            <option value="range">Range / Sideways ↔</option>
          </select>
        );
      case "session":
        return (
          <select value={newValue} onChange={(e) => setNewValue(e.target.value)} style={styles.select}>
            <option value="asia">Asia 🌏</option>
            <option value="london">London 🇬🇧</option>
            <option value="new_york">New York 🗽</option>
          </select>
        );
      case "free_notes":
        return (
          <textarea
            placeholder="Ketikkan catatan bebas baru..."
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            style={styles.textarea}
          />
        );
      default:
        return (
          <input
            type="text"
            placeholder="Masukkan nilai baru..."
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            style={styles.input}
          />
        );
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <div>
            <h3 style={styles.title}>📝 Ajukan Koreksi Data Trade</h3>
            <span style={styles.subtitle}>
              Trade ini terkunci permanen. Koreksi akan memperbarui tampilan dan dicatat dalam audit log.
            </span>
          </div>
          <button style={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        {error && <div style={styles.errorBox}>{error}</div>}
        {successMsg && <div style={styles.successBox}>{successMsg}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>1. Field yang Ingin Dikoreksi (Wajib)</label>
            <select
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              style={styles.select}
            >
              {FIELD_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div style={styles.gridTwo}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>2. Nilai Saat Ini (Otomatis)</label>
              <div style={styles.readOnlyPill}>{oldValue}</div>
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>3. Nilai Baru (File/Pilihan Terstruktur)</label>
              {renderNewValueInput()}
            </div>
          </div>

          <div style={styles.inputGroup}>
            <div style={styles.labelRow}>
              <label style={styles.label}>4. Alasan Koreksi (Min 10 Karakter - Wajib)</label>
              <span
                style={{
                  ...styles.counterText,
                  color: reasonLen >= 10 ? "#34d399" : "#f87171",
                }}
              >
                {reasonLen} / 10 karakter minimum
              </span>
            </div>
            <textarea
              placeholder="Jelaskan alasan pembaruan data secara objektif (min 10 karakter)..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              style={styles.textarea}
            />
          </div>

          <div style={styles.actions}>
            <button type="button" onClick={onClose} style={styles.cancelBtn}>
              Batal
            </button>
            <button
              type="submit"
              disabled={loading || reasonLen < 10}
              style={{
                ...styles.submitBtn,
                ...(loading || reasonLen < 10 ? styles.submitBtnDisabled : {}),
              }}
            >
              {loading ? "Menerapkan Koreksi..." : "Kirim & Terapkan Koreksi →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.8)",
    backdropFilter: "blur(8px)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 9999,
    padding: "20px",
  },
  modal: {
    backgroundColor: "rgba(22, 19, 39, 0.95)",
    border: "1px solid rgba(124, 58, 237, 0.4)",
    borderRadius: "16px",
    width: "100%",
    maxWidth: "580px",
    padding: "26px",
    boxShadow: "0 20px 50px rgba(0, 0, 0, 0.6)",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
    paddingBottom: "14px",
  },
  title: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#ffffff",
    margin: "0 0 4px 0",
  },
  subtitle: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  closeBtn: {
    backgroundColor: "transparent",
    border: "none",
    color: "#94a3b8",
    fontSize: "18px",
    cursor: "pointer",
  },
  errorBox: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "8px",
    color: "#f87171",
    padding: "12px",
    fontSize: "13px",
  },
  successBox: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    borderRadius: "8px",
    color: "#34d399",
    padding: "12px",
    fontSize: "13px",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  gridTwo: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "16px",
  },
  labelRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  label: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#cbd5e1",
  },
  counterText: {
    fontSize: "11px",
    fontWeight: "700",
  },
  select: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    color: "#ffffff",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    outline: "none",
  },
  readOnlyPill: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    border: "1px dashed rgba(255, 255, 255, 0.2)",
    color: "#94a3b8",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "700",
    minHeight: "41px",
    display: "flex",
    alignItems: "center",
    wordBreak: "break-all",
  },
  filePickerBox: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  filePickerLabel: {
    backgroundColor: "rgba(124, 58, 237, 0.15)",
    border: "1px dashed #7c3aed",
    color: "#a78bfa",
    padding: "8px 12px",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: "700",
    cursor: "pointer",
    textAlign: "center",
  },
  selectedFilePill: {
    backgroundColor: "rgba(16, 185, 129, 0.12)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    borderRadius: "6px",
    color: "#34d399",
    padding: "6px 10px",
    fontSize: "11px",
    fontWeight: "600",
  },
  filePickerHint: {
    fontSize: "11px",
    color: "#64748b",
  },
  input: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    color: "#ffffff",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    outline: "none",
  },
  textarea: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    color: "#ffffff",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    minHeight: "80px",
    resize: "vertical",
    outline: "none",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "12px",
    marginTop: "8px",
  },
  cancelBtn: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    color: "#94a3b8",
    padding: "10px 18px",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: "600",
    cursor: "pointer",
  },
  submitBtn: {
    backgroundColor: "#7c3aed",
    border: "none",
    color: "#ffffff",
    padding: "10px 20px",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: "700",
    cursor: "pointer",
    boxShadow: "0 4px 15px rgba(124, 58, 237, 0.3)",
    transition: "all 0.2s ease",
  },
  submitBtnDisabled: {
    backgroundColor: "rgba(255, 255, 255, 0.05)",
    color: "#64748b",
    boxShadow: "none",
    cursor: "not-allowed",
  },
};

export default CorrectionModal;
