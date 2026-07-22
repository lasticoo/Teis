import React, { useState } from "react";

const FIELD_OPTIONS = [
  { value: "confidence_level", label: "Tingkat Keyakinan (Confidence Level)" },
  { value: "plan_adherence", label: "Kepatuhan pada Plan (Plan Adherence)" },
  { value: "psychological_tags", label: "Kondisi Emosional Saat Entry" },
  { value: "bias_arah_manual", label: "Bias Arah Trend (Bull/Bear/Range)" },
  { value: "session", label: "Sesi Trading (Asia/London/NY)" },
  { value: "free_notes", label: "Catatan Bebas (Free Notes)" },
  { value: "setup_tags", label: "Tag Model Setup Trade" },
  { value: "order_type", label: "Tipe Order (Limit / Market)" },
  { value: "moved_to_breakeven", label: "Koreksi Status Breakeven (BE)" },
  { value: "trailing_stop_used", label: "Koreksi Status Trailing Stop" },
];

const CorrectionModal = ({ isOpen, onClose, tradeId, onSuccess }) => {
  const [fieldName, setFieldName] = useState("confidence_level");
  const [oldValue, setOldValue] = useState("");
  const [newValue, setNewValue] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");

    const cleanReason = reason.strip ? reason.strip() : reason.trim();
    if (cleanReason.length < 10) {
      setError("Alasan koreksi wajib diisi minimal 10 karakter.");
      return;
    }

    if (!newValue.trim()) {
      setError("Nilai baru wajib diisi.");
      return;
    }

    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/journal/correct", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          original_trade_id: tradeId,
          field_name: fieldName,
          old_value: oldValue || null,
          new_value: newValue,
          reason: cleanReason,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gagal mengajukan koreksi.");
      }

      setSuccessMsg("✅ Koreksi data trade berhasil dicatat dalam audit log.");
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

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <div>
            <h3 style={styles.title}>📝 Ajukan Koreksi Data Trade</h3>
            <span style={styles.subtitle}>
              Trade ini telah terkunci permanen. Seluruh koreksi akan dicatat dalam audit log trade_corrections.
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
            <label style={styles.label}>1. Field yang Dikoreksi (Wajib)</label>
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
              <label style={styles.label}>2. Nilai Lama (Old Value)</label>
              <input
                type="text"
                placeholder="Contoh: 5 (opsional)"
                value={oldValue}
                onChange={(e) => setOldValue(e.target.value)}
                style={styles.input}
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>3. Nilai Baru (New Value - Wajib)</label>
              <input
                type="text"
                placeholder="Contoh: 8"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                style={styles.input}
              />
            </div>
          </div>

          <div style={styles.inputGroup}>
            <div style={styles.labelRow}>
              <label style={styles.label}>4. Alasan Koreksi (Reason - Wajib Minimal 10 Karakter)</label>
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
              {loading ? "Menyimpan Audit..." : "Kirim Koreksi Audit →"}
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
    border: "1px solid rgba(255, 255, 255, 0.12)",
    color: "#ffffff",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    outline: "none",
  },
  input: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    color: "#ffffff",
    padding: "10px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    outline: "none",
  },
  textarea: {
    backgroundColor: "rgba(15, 12, 30, 0.9)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
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
