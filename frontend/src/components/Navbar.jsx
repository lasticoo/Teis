import React, { useEffect, useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);

  const fetchPendingCount = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      const response = await fetch("http://localhost:8000/api/v1/trades/pending-count", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setPendingCount(data.count);
      }
    } catch (error) {
      console.error("Gagal mengambil jumlah trade pending:", error);
    }
  };

  useEffect(() => {
    fetchPendingCount();
    // Poll count every 15 seconds to keep Navbar updated
    const interval = setInterval(fetchPendingCount, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav style={styles.navbar}>
      <div style={styles.logoContainer}>
        <div style={styles.logoGlow}></div>
        <span style={styles.logoText}>TEIS</span>
        <span style={styles.logoSub}>Trading Edge</span>
      </div>

      <div style={styles.navLinks}>
        <Link
          to="/settings"
          style={location.pathname === "/settings" ? styles.activeLink : styles.link}
        >
          Settings
        </Link>
      </div>

      <div style={styles.rightSection}>
        {/* Pending tag notification indicator */}
        <div style={styles.notificationWrapper} title={`${pendingCount} trade perlu ditag`}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            style={pendingCount > 0 ? styles.bellIconActive : styles.bellIcon}
          >
            <path fillRule="evenodd" d="M5.25 9a6.75 6.75 0 0 1 13.5 0v.75c0 2.123.8 4.057 2.118 5.52a.75.75 0 0 1-.297 1.206c-1.544.57-3.16.99-4.831 1.243a3.75 3.75 0 1 1-7.48 0 24.585 24.585 0 0 1-4.831-1.244.75.75 0 0 1-.298-1.205A8.217 8.217 0 0 0 5.25 9.75V9Zm4.502 8.9a2.25 2.25 0 1 0 4.496 0 25.057 25.057 0 0 1-4.496 0Z" clipRule="evenodd" />
          </svg>
          {pendingCount > 0 && (
            <span style={styles.badge}>{pendingCount}</span>
          )}
        </div>

        <button onClick={handleLogout} style={styles.logoutButton}>
          Keluar
        </button>
      </div>
    </nav>
  );
}

const styles = {
  navbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0 2rem",
    height: "70px",
    background: "rgba(18, 16, 26, 0.75)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderBottom: "1px solid rgba(139, 92, 246, 0.15)",
    position: "sticky",
    top: 0,
    zIndex: 1000,
    boxShadow: "0 4px 30px rgba(0, 0, 0, 0.4)",
  },
  logoContainer: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    position: "relative",
  },
  logoGlow: {
    position: "absolute",
    width: "40px",
    height: "40px",
    borderRadius: "50%",
    background: "rgba(139, 92, 246, 0.4)",
    filter: "blur(15px)",
    left: "-10px",
  },
  logoText: {
    fontSize: "1.5rem",
    fontWeight: 800,
    color: "#fff",
    letterSpacing: "1.5px",
    background: "linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  logoSub: {
    fontSize: "0.75rem",
    color: "#a78bfa",
    textTransform: "uppercase",
    letterSpacing: "1px",
    borderLeft: "1px solid rgba(167, 139, 250, 0.3)",
    paddingLeft: "0.5rem",
    fontWeight: 500,
  },
  navLinks: {
    display: "flex",
    gap: "2rem",
  },
  link: {
    color: "#9ca3af",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: "0.95rem",
    transition: "color 0.2s",
  },
  activeLink: {
    color: "#a78bfa",
    textDecoration: "none",
    fontWeight: 600,
    fontSize: "0.95rem",
    borderBottom: "2px solid #8b5cf6",
    paddingBottom: "0.25rem",
  },
  rightSection: {
    display: "flex",
    alignItems: "center",
    gap: "1.5rem",
  },
  notificationWrapper: {
    position: "relative",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  bellIcon: {
    width: "24px",
    height: "24px",
    color: "#9ca3af",
    transition: "color 0.2s",
  },
  bellIconActive: {
    width: "24px",
    height: "24px",
    color: "#ef4444",
    filter: "drop-shadow(0 0 6px rgba(239, 68, 68, 0.6))",
    animation: "pulseBell 2s infinite",
  },
  badge: {
    position: "absolute",
    top: "-5px",
    right: "-8px",
    background: "#ef4444",
    color: "#fff",
    fontSize: "0.7rem",
    fontWeight: 700,
    borderRadius: "50%",
    width: "16px",
    height: "16px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 0 10px rgba(239, 68, 68, 0.8)",
  },
  logoutButton: {
    background: "transparent",
    border: "1px solid rgba(156, 163, 175, 0.3)",
    color: "#9ca3af",
    padding: "0.5rem 1rem",
    borderRadius: "6px",
    fontSize: "0.85rem",
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 0.2s",
  },
};
