import React, { useState, useEffect } from "react";
import { useAuth, API_URL } from "../context/AuthContext";

const Settings = () => {
  const { getAuthHeader, logout } = useAuth();
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });
  const [showKeys, setShowKeys] = useState(false);

  useEffect(() => {
    fetchKeyStatus();
  }, []);

  const fetchKeyStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/settings/binance-key`, {
        headers: getAuthHeader(),
      });
      if (response.ok) {
        const data = await response.json();
        setHasKey(data.has_key);
      }
    } catch (e) {
      console.error("Gagal memuat status API Key Binance.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveKeys = async (e) => {
    e.preventDefault();
    setMessage({ text: "", type: "" });
    setSaving(true);

    try {
      const response = await fetch(`${API_URL}/settings/binance-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeader(),
        },
        body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Gagal menyimpan API Key.");
      }

      setMessage({ text: "Kunci API Binance berhasil disimpan dan dienkripsi.", type: "success" });
      setHasKey(true);
      setApiKey("");
      setApiSecret("");
    } catch (err) {
      setMessage({ text: err.message || "Gagal menyimpan API Key.", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={styles.loading}>Memuat pengaturan...</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.mainContent}>
        <h1 style={styles.pageTitle}>Pengaturan Sistem</h1>
        <p style={styles.pageSubtitle}>Konfigurasi kredensial Binance API dan preferensi keamanan Anda.</p>

        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.sectionTitle}>Koneksi API Binance Futures</h2>
            <div style={hasKey ? styles.statusBadgeSynced : styles.statusBadgeNotSynced}>
              {hasKey ? "Tersambung (Terdeskripsi)" : "Kunci Belum Ditambahkan"}
            </div>
          </div>

          <p style={styles.infoText}>
            Masukkan API Key Binance dengan hak akses <strong>Read-only (pembacaan)</strong>.
            Jangan aktifkan akses Spot Trading, margin, atau penarikan dana (withdrawal) demi alasan keamanan. Kunci akan dienkripsi menggunakan AES-256-GCM.
          </p>

          {message.text && (
            <div style={message.type === "success" ? styles.successAlert : styles.errorAlert}>
              {message.text}
            </div>
          )}

          <form onSubmit={handleSaveKeys} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Binance API Key</label>
              <input
                type={showKeys ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={hasKey ? "••••••••••••••••••••••••••••••••" : "Masukkan API Key Binance"}
                required={!hasKey}
                style={styles.input}
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Binance API Secret</label>
              <input
                type={showKeys ? "text" : "password"}
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder={hasKey ? "••••••••••••••••••••••••••••••••" : "Masukkan API Secret Binance"}
                required={!hasKey}
                style={styles.input}
              />
            </div>

            <div style={styles.optionsRow}>
              <label style={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={showKeys}
                  onChange={() => setShowKeys(!showKeys)}
                  style={styles.checkbox}
                />
                Tampilkan Kunci API
              </label>
            </div>

            <button type="submit" disabled={saving} style={styles.button}>
              {saving ? "Menyimpan..." : "Simpan Kunci API"}
            </button>
          </form>
        </div>

        <div style={styles.footer}>
          <div style={styles.connectionStatus}>
            <span style={hasKey ? styles.statusDotConnected : styles.statusDotDisconnected}></span>
            <span style={styles.statusText}>
              Koneksi API Binance Futures: <strong>{hasKey ? "Connected (Decrypted)" : "Disconnected"}</strong>
            </span>
          </div>
          <div style={styles.footerText}>
            Trading Edge Intelligence System &copy; 2026
          </div>
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    minHeight: "calc(100vh - 70px)",
    backgroundColor: "#0d0a1b",
    fontFamily: "'Inter', sans-serif",
    color: "#e2e8f0",
  },
  loading: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    backgroundColor: "#0d0a1b",
    color: "#ffffff",
    fontSize: "18px",
  },
  mainContent: {
    flex: 1,
    padding: "40px 50px",
    maxWidth: "1200px",
    margin: "0 auto",
    width: "100%",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
  },
  pageTitle: {
    fontSize: "28px",
    fontWeight: "700",
    color: "#ffffff",
    margin: "0 0 8px 0",
  },
  pageSubtitle: {
    fontSize: "14px",
    color: "#94a3b8",
    margin: "0 0 40px 0",
  },
  sectionCard: {
    backgroundColor: "rgba(22, 19, 39, 0.6)",
    borderRadius: "12px",
    border: "1px solid rgba(255, 255, 255, 0.06)",
    padding: "30px",
    maxWidth: "800px",
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "20px",
  },
  sectionTitle: {
    fontSize: "18px",
    fontWeight: "600",
    color: "#ffffff",
    margin: 0,
  },
  statusBadgeSynced: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    color: "#34d399",
    fontSize: "12px",
    fontWeight: "600",
    padding: "4px 12px",
    borderRadius: "20px",
  },
  statusBadgeNotSynced: {
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    border: "1px solid rgba(245, 158, 11, 0.3)",
    color: "#fbbf24",
    fontSize: "12px",
    fontWeight: "600",
    padding: "4px 12px",
    borderRadius: "20px",
  },
  infoText: {
    fontSize: "14px",
    color: "#94a3b8",
    lineHeight: "1.6",
    marginBottom: "30px",
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
  input: {
    backgroundColor: "#161327",
    color: "#ffffff",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: "8px",
    padding: "12px 16px",
    fontSize: "14px",
    outline: "none",
    fontFamily: "monospace",
  },
  optionsRow: {
    display: "flex",
    alignItems: "center",
  },
  checkboxLabel: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "13px",
    color: "#94a3b8",
    cursor: "pointer",
  },
  checkbox: {
    cursor: "pointer",
  },
  button: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "14px",
    fontSize: "15px",
    fontWeight: "600",
    cursor: "pointer",
    alignSelf: "flex-start",
    paddingLeft: "30px",
    paddingRight: "30px",
    transition: "background-color 0.2s",
    boxShadow: "0 4px 15px rgba(124, 58, 237, 0.3)",
  },
  successAlert: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    borderRadius: "8px",
    padding: "14px",
    color: "#34d399",
    fontSize: "14px",
    marginBottom: "25px",
  },
  errorAlert: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "8px",
    padding: "14px",
    color: "#f87171",
    fontSize: "14px",
    marginBottom: "25px",
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "40px",
    paddingTop: "20px",
    borderTop: "1px solid rgba(255, 255, 255, 0.05)",
    color: "#94a3b8",
    fontSize: "13px",
  },
  connectionStatus: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  statusDotConnected: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: "#10b981",
    boxShadow: "0 0 8px #10b981",
  },
  statusDotDisconnected: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: "#ef4444",
    boxShadow: "0 0 8px #ef4444",
  },
  statusText: {
    color: "#e2e8f0",
  },
  footerText: {
    color: "#64748b",
  },
};

export default Settings;
