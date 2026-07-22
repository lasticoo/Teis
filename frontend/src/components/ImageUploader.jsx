import React, { useState, useEffect } from "react";

const ImageUploader = ({
  tradeId,
  stage = "before_entry",
  stageLabel = "Chart Screenshot",
  currentImageUrl = null,
  isLocked = false,
  onUploadSuccess,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [previewUrl, setPreviewUrl] = useState(currentImageUrl);

  const isBeforeEntryLocked = stage === "before_entry" && isLocked;

  useEffect(() => {
    if (currentImageUrl) {
      const cacheBusted = currentImageUrl.includes("?")
        ? `${currentImageUrl}&t=${Date.now()}`
        : `${currentImageUrl}?t=${Date.now()}`;
      setPreviewUrl(cacheBusted);
    }
  }, [currentImageUrl]);

  const handleFileSelect = async (file) => {
    if (!file) return;
    if (isBeforeEntryLocked) {
      setError("Screenshot 'Sebelum Entry' terkunci. Ajukan Koreksi untuk mengubahnya.");
      return;
    }

    setError("");
    setSuccessMsg("");

    const maxSizeBytes = 5 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      setError("Ukuran file melebihi batas maksimal 5MB.");
      return;
    }
    if (!file.type.startsWith("image/")) {
      setError("File harus berupa gambar valid (PNG, JPG, WEBP).");
      return;
    }

    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const formData = new FormData();
    formData.append("trade_id", tradeId);
    formData.append("stage", stage);
    formData.append("file", file);

    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/screenshots/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mengunggah gambar.");

      setSuccessMsg("✅ Gambar berhasil diunggah & dikompres WebP 80%");

      const rawUrl = data.screenshot?.url || URL.createObjectURL(file);
      const cacheBustedUrl = rawUrl.includes("?")
        ? `${rawUrl}&t=${Date.now()}`
        : `${rawUrl}?t=${Date.now()}`;

      setPreviewUrl(cacheBustedUrl);

      if (onUploadSuccess) onUploadSuccess(data.screenshot);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isBeforeEntryLocked) return;
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (isBeforeEntryLocked) return;
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) handleFileSelect(e.target.files[0]);
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.headerRow}>
        <span style={styles.label}>{stageLabel}</span>
        {isBeforeEntryLocked ? (
          <span style={styles.lockedChip}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            Imutabel
          </span>
        ) : (
          <span style={styles.maxSizeHint}>Max 5MB • WebP 80%</span>
        )}
      </div>

      {/* Messages */}
      {error && <div style={styles.errorBox}>{error}</div>}
      {successMsg && <div style={styles.successBox}>{successMsg}</div>}

      {/* Content Area */}
      {loading ? (
        <div style={styles.loadingContainer}>
          <div style={styles.spinner} />
          <span style={styles.loadingText}>Mengompresi & mengunggah...</span>
        </div>
      ) : previewUrl ? (
        <div style={styles.previewContainer}>
          <img
            src={previewUrl}
            alt={stageLabel}
            style={styles.previewImg}
            onClick={() => window.open(previewUrl, "_blank")}
          />
          <div style={styles.previewOverlay}>
            <button
              type="button"
              onClick={() => window.open(previewUrl, "_blank")}
              style={styles.zoomBtn}
            >
              ⛶ Lihat
            </button>
            {isBeforeEntryLocked ? (
              <span style={styles.lockedOverlayChip}>
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 3 }}>
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                Ajukan Koreksi
              </span>
            ) : (
              <label style={styles.reuploadBtn}>
                📷 Ganti
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleChange}
                  style={{ display: "none" }}
                />
              </label>
            )}
          </div>
        </div>
      ) : (
        /* Dropzone */
        <div
          style={{
            ...styles.dropzone,
            ...(dragActive ? styles.dropzoneActive : {}),
            ...(isBeforeEntryLocked ? styles.dropzoneDisabled : {}),
          }}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          {isBeforeEntryLocked ? (
            <div style={styles.dropzoneContentDisabled}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span style={styles.dropTextMuted}>Terkunci — perubahan via Ajukan Koreksi</span>
            </div>
          ) : (
            <label style={styles.dropzoneContent}>
              <span style={styles.uploadIcon}>📁</span>
              <span style={styles.dropText}>
                Drag & drop atau <span style={styles.browseLink}>pilih file</span>
              </span>
              <span style={styles.subDropText}>PNG, JPG, WEBP • Max 5MB</span>
              <input
                type="file"
                accept="image/*"
                onChange={handleChange}
                style={{ display: "none" }}
              />
            </label>
          )}
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    backgroundColor: "rgba(15, 12, 30, 0.6)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderRadius: "12px",
    padding: "16px",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  label: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#e2e8f0",
  },
  maxSizeHint: {
    fontSize: "11px",
    color: "#475569",
  },
  /* Subtle grey chip — not aggressive red */
  lockedChip: {
    display: "inline-flex",
    alignItems: "center",
    fontSize: "10px",
    fontWeight: "600",
    color: "#64748b",
    backgroundColor: "rgba(100, 116, 139, 0.12)",
    border: "1px solid rgba(100, 116, 139, 0.2)",
    padding: "2px 8px",
    borderRadius: "20px",
    letterSpacing: "0.3px",
  },
  errorBox: {
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    border: "1px solid rgba(239, 68, 68, 0.25)",
    borderRadius: "6px",
    color: "#f87171",
    padding: "7px 12px",
    fontSize: "12px",
  },
  successBox: {
    backgroundColor: "rgba(16, 185, 129, 0.1)",
    border: "1px solid rgba(16, 185, 129, 0.25)",
    borderRadius: "6px",
    color: "#34d399",
    padding: "7px 12px",
    fontSize: "12px",
  },
  dropzone: {
    border: "2px dashed rgba(124, 58, 237, 0.3)",
    borderRadius: "10px",
    padding: "28px 16px",
    textAlign: "center",
    backgroundColor: "rgba(124, 58, 237, 0.03)",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  dropzoneDisabled: {
    border: "1px dashed rgba(100, 116, 139, 0.2)",
    backgroundColor: "transparent",
    cursor: "default",
  },
  dropzoneActive: {
    borderColor: "#7c3aed",
    backgroundColor: "rgba(124, 58, 237, 0.1)",
  },
  dropzoneContent: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    cursor: "pointer",
  },
  dropzoneContentDisabled: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "8px",
    padding: "12px 0",
    cursor: "default",
  },
  uploadIcon: {
    fontSize: "22px",
  },
  dropText: {
    fontSize: "13px",
    color: "#cbd5e1",
  },
  dropTextMuted: {
    fontSize: "12px",
    color: "#475569",
  },
  browseLink: {
    color: "#a78bfa",
    fontWeight: "700",
    textDecoration: "underline",
  },
  subDropText: {
    fontSize: "11px",
    color: "#475569",
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    height: "140px",
    backgroundColor: "rgba(124, 58, 237, 0.04)",
    borderRadius: "10px",
    border: "1px dashed rgba(124, 58, 237, 0.3)",
  },
  spinner: {
    width: "24px",
    height: "24px",
    border: "2px solid rgba(255, 255, 255, 0.08)",
    borderTop: "2px solid #7c3aed",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    fontSize: "12px",
    color: "#64748b",
  },
  previewContainer: {
    position: "relative",
    borderRadius: "8px",
    overflow: "hidden",
    border: "1px solid rgba(255, 255, 255, 0.07)",
    height: "200px",
    backgroundColor: "#05040a",
  },
  previewImg: {
    width: "100%",
    height: "100%",
    objectFit: "contain",
    display: "block",
    cursor: "pointer",
  },
  previewOverlay: {
    position: "absolute",
    bottom: "8px",
    right: "8px",
    display: "flex",
    gap: "6px",
  },
  zoomBtn: {
    backgroundColor: "rgba(0, 0, 0, 0.65)",
    color: "#94a3b8",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    padding: "5px 10px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "600",
    cursor: "pointer",
  },
  reuploadBtn: {
    backgroundColor: "rgba(124, 58, 237, 0.75)",
    color: "#ffffff",
    border: "none",
    padding: "5px 10px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "600",
    cursor: "pointer",
  },
  /* Subtle muted chip shown on top of image when locked */
  lockedOverlayChip: {
    display: "inline-flex",
    alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.55)",
    color: "#94a3b8",
    border: "1px solid rgba(255,255,255,0.1)",
    padding: "5px 10px",
    borderRadius: "6px",
    fontSize: "10px",
    fontWeight: "600",
    cursor: "default",
    backdropFilter: "blur(4px)",
  },
};

export default ImageUploader;
