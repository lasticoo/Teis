import React, { useState, useEffect } from "react";

const ImageUploader = ({
  tradeId,
  stage = "before_entry",
  stageLabel = "Chart Screenshot",
  currentImageUrl = null,
  onUploadSuccess,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [previewUrl, setPreviewUrl] = useState(currentImageUrl);

  useEffect(() => {
    if (currentImageUrl) {
      setPreviewUrl(currentImageUrl);
    }
  }, [currentImageUrl]);

  const handleFileSelect = async (file) => {
    if (!file) return;

    setError("");
    setSuccessMsg("");

    // 1. Client-side size check (5MB)
    const maxSizeBytes = 5 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      setError("Ukuran file melebihi batas maksimal 5MB.");
      return;
    }

    // 2. Client-side image MIME type check
    if (!file.type.startsWith("image/")) {
      setError("File harus berupa gambar valid (PNG, JPG, WEBP).");
      return;
    }

    // Prepare upload
    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const formData = new FormData();
    formData.append("trade_id", tradeId);
    formData.append("stage", stage);
    formData.append("file", file);

    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/screenshots/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gagal mengunggah gambar ke MinIO.");
      }

      setSuccessMsg("✅ WebP 80% compressed & saved to MinIO S3!");
      const newUrl = data.screenshot?.url || URL.createObjectURL(file);
      setPreviewUrl(newUrl);

      if (onUploadSuccess) {
        onUploadSuccess(data.screenshot);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.headerRow}>
        <span style={styles.label}>{stageLabel}</span>
        <span style={styles.maxSizeHint}>Max 5MB • WebP 80% Auto Compress</span>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}
      {successMsg && <div style={styles.successBox}>{successMsg}</div>}

      {/* Preview if image exists */}
      {previewUrl ? (
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
              🔍 Open Full
            </button>
            <label style={styles.reuploadBtn}>
              📷 Ganti Gambar
              <input
                type="file"
                accept="image/*"
                onChange={handleChange}
                style={{ display: "none" }}
              />
            </label>
          </div>
        </div>
      ) : (
        /* Dropzone Upload Area */
        <div
          style={{
            ...styles.dropzone,
            ...(dragActive ? styles.dropzoneActive : {}),
          }}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          {loading ? (
            <div style={styles.loadingWrapper}>
              <div style={styles.spinner} />
              <span style={styles.loadingText}>⚙️ Kompresi WebP 80% & Uploading MinIO S3...</span>
            </div>
          ) : (
            <label style={styles.dropzoneContent}>
              <span style={styles.uploadIcon}>📁</span>
              <span style={styles.dropText}>
                Drag & Drop file gambar di sini, atau <span style={styles.browseLink}>Pilih File</span>
              </span>
              <span style={styles.subDropText}>Format yang didukung: PNG, JPG, WEBP (Max 5MB)</span>
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
    color: "#64748b",
  },
  errorBox: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "6px",
    color: "#f87171",
    padding: "8px 12px",
    fontSize: "12px",
  },
  successBox: {
    backgroundColor: "rgba(16, 185, 129, 0.15)",
    border: "1px solid rgba(16, 185, 129, 0.3)",
    borderRadius: "6px",
    color: "#34d399",
    padding: "8px 12px",
    fontSize: "12px",
  },
  dropzone: {
    border: "2px dashed rgba(124, 58, 237, 0.35)",
    borderRadius: "10px",
    padding: "24px 16px",
    textAlign: "center",
    backgroundColor: "rgba(124, 58, 237, 0.04)",
    cursor: "pointer",
    transition: "all 0.2s ease",
  },
  dropzoneActive: {
    borderColor: "#7c3aed",
    backgroundColor: "rgba(124, 58, 237, 0.12)",
  },
  dropzoneContent: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    cursor: "pointer",
  },
  uploadIcon: {
    fontSize: "24px",
  },
  dropText: {
    fontSize: "13px",
    color: "#cbd5e1",
  },
  browseLink: {
    color: "#a78bfa",
    fontWeight: "700",
    textDecoration: "underline",
  },
  subDropText: {
    fontSize: "11px",
    color: "#64748b",
  },
  loadingWrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "10px",
  },
  spinner: {
    width: "24px",
    height: "24px",
    border: "3px solid rgba(255, 255, 255, 0.1)",
    borderTop: "3px solid #7c3aed",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  loadingText: {
    fontSize: "12px",
    color: "#a78bfa",
    fontWeight: "600",
  },
  previewContainer: {
    position: "relative",
    borderRadius: "8px",
    overflow: "hidden",
    border: "1px solid rgba(255, 255, 255, 0.1)",
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
    gap: "8px",
  },
  zoomBtn: {
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    color: "#a78bfa",
    border: "1px solid rgba(167, 139, 250, 0.4)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
    cursor: "pointer",
  },
  reuploadBtn: {
    backgroundColor: "rgba(0, 0, 0, 0.75)",
    color: "#ffffff",
    border: "1px solid rgba(255, 255, 255, 0.2)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "11px",
    fontWeight: "700",
    cursor: "pointer",
  },
};

export default ImageUploader;
