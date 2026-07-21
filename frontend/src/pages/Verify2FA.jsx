import React, { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const Verify2FA = () => {
  const { verify2FA } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [code, setCode] = useState(new Array(6).fill(""));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRefs = useRef([]);

  const sessionToken = location.state?.sessionToken;

  useEffect(() => {
    if (!sessionToken) {
      navigate("/login");
    }
  }, [sessionToken, navigate]);

  const handleChange = (element, index) => {
    if (isNaN(element.value)) return false;

    const newCode = [...code];
    newCode[index] = element.value;
    setCode(newCode);

    // Auto-focus next input box
    if (element.value !== "" && index < 5) {
      inputRefs.current[index + 1].focus();
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && index > 0 && code[index] === "") {
      inputRefs.current[index - 1].focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasteData = e.clipboardData.getData("text").trim();
    if (pasteData.length === 6 && /^\d+$/.test(pasteData)) {
      const newCode = pasteData.split("");
      setCode(newCode);
      inputRefs.current[5].focus();
    }
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    const totpCode = code.join("");
    if (totpCode.length !== 6) {
      setError("Kode harus terdiri dari 6 angka.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      await verify2FA(totpCode, sessionToken);
      navigate("/");
    } catch (err) {
      setError(err.message || "Kode 2FA salah atau kedaluwarsa.");
      // Clear inputs on failure
      setCode(new Array(6).fill(""));
      inputRefs.current[0].focus();
    } finally {
      setLoading(false);
    }
  };

  // Auto-submit when all 6 digits are filled
  useEffect(() => {
    if (code.every((digit) => digit !== "")) {
      handleSubmit();
    }
  }, [code]);

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logoContainer}>
          <div style={styles.logoBadge}>2FA REQUIRED</div>
          <h2 style={styles.title}>Verifikasi Dua Faktor</h2>
          <p style={styles.subtitle}>Masukkan 6 digit kode dari Google Authenticator</p>
        </div>

        {error && <div style={styles.errorAlert}>{error}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.codeContainer}>
            {code.map((data, index) => (
              <input
                key={index}
                type="text"
                maxLength="1"
                ref={(el) => (inputRefs.current[index] = el)}
                value={data}
                onChange={(e) => handleChange(e.target, index)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                onPaste={index === 0 ? handlePaste : undefined}
                style={styles.codeInput}
                disabled={loading}
              />
            ))}
          </div>

          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "Memverifikasi..." : "Verifikasi"}
          </button>
        </form>

        <div style={styles.footer}>
          <button onClick={() => navigate("/login")} style={styles.cancelBtn}>
            Kembali ke Login
          </button>
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    backgroundColor: "#0d0a1b",
    fontFamily: "'Inter', sans-serif",
    padding: "20px",
  },
  card: {
    width: "100%",
    maxWidth: "420px",
    backgroundColor: "rgba(22, 19, 39, 0.75)",
    backdropFilter: "blur(12px)",
    borderRadius: "16px",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
    padding: "40px 30px",
    color: "#e2e8f0",
  },
  logoContainer: {
    textAlign: "center",
    marginBottom: "35px",
  },
  logoBadge: {
    display: "inline-block",
    backgroundColor: "#ff007f",
    color: "#ffffff",
    fontWeight: "bold",
    fontSize: "12px",
    padding: "4px 12px",
    borderRadius: "20px",
    marginBottom: "12px",
    boxShadow: "0 0 15px rgba(255, 0, 127, 0.4)",
  },
  title: {
    fontSize: "20px",
    fontWeight: "700",
    color: "#ffffff",
    margin: "0 0 8px 0",
  },
  subtitle: {
    fontSize: "13px",
    color: "#94a3b8",
    margin: 0,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "25px",
  },
  codeContainer: {
    display: "flex",
    justifyContent: "space-between",
    gap: "8px",
  },
  codeInput: {
    width: "48px",
    height: "56px",
    backgroundColor: "#161327",
    color: "#ffffff",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: "8px",
    fontSize: "24px",
    fontWeight: "600",
    textAlign: "center",
    outline: "none",
    transition: "border-color 0.2s, box-shadow 0.2s",
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
    transition: "background-color 0.2s",
    boxShadow: "0 4px 15px rgba(124, 58, 237, 0.3)",
  },
  errorAlert: {
    backgroundColor: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "8px",
    padding: "12px",
    color: "#f87171",
    fontSize: "13px",
    marginBottom: "20px",
    textAlign: "center",
  },
  footer: {
    textAlign: "center",
    marginTop: "20px",
  },
  cancelBtn: {
    background: "none",
    border: "none",
    color: "#94a3b8",
    fontSize: "13px",
    cursor: "pointer",
    textDecoration: "underline",
  },
};

export default Verify2FA;
