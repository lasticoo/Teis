import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NotificationBanner from "./NotificationBanner";
import NotificationBell from "./NotificationBell";


export default function Navbar() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [bannerNotification, setBannerNotification] = useState(null);

  const fetchNotifications = useCallback(async () => {
    try {
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) return;

      const res = await fetch("http://localhost:8000/api/v1/notifications", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);

        // Find active pending tag notification for banner
        const pendingTag = (data.notifications || []).find((n) => n.type === "trade_pending_tag");
        if (pendingTag) {
          setBannerNotification(pendingTag);
        } else if (data.notifications && data.notifications.length > 0) {
          setBannerNotification(data.notifications[0]);
        } else {
          setBannerNotification(null);
        }
      }
    } catch (err) {
      console.error("Gagal mengambil daftar notifikasi:", err);
    }
  }, []);

  const acknowledgeNotification = async (notificationId) => {
    try {
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      await fetch(`http://localhost:8000/api/v1/notifications/acknowledge/${notificationId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
      setUnreadCount((prev) => Math.max(0, prev - 1));
      if (bannerNotification && bannerNotification.id === notificationId) {
        setBannerNotification(null);
      }
    } catch (err) {
      console.error("Gagal meng-acknowledge notifikasi:", err);
    }
  };

  const acknowledgeAllNotifications = async () => {
    try {
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      await fetch("http://localhost:8000/api/v1/notifications/acknowledge-all", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications([]);
      setUnreadCount(0);
      setBannerNotification(null);
    } catch (err) {
      console.error("Gagal meng-acknowledge semua notifikasi:", err);
    }
  };

  useEffect(() => {
    fetchNotifications();

    // 1. Establish WebSocket connection for real-time alerts

    const token = localStorage.getItem("token") || localStorage.getItem("access_token");
    const wsUrl = `ws://localhost:8000/api/v1/notifications/ws${token ? `?token=${token}` : ""}`;
    let socket = null;

    try {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log("⚡ Connected to TEIS Real-Time Notification WebSocket.");
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("🔔 Real-time notification received via WebSocket:", data);
          fetchNotifications();
        } catch (e) {
          console.warn("Raw WS message:", event.data);
        }
      };

      socket.onerror = (err) => {
        console.warn("WebSocket notification error:", err);
      };
    } catch (e) {
      console.warn("Failed to initialize WebSocket:", e);
    }

    const interval = setInterval(fetchNotifications, 15000);

    return () => {
      clearInterval(interval);
      if (socket) socket.close();
    };
  }, [fetchNotifications]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <>
      <NotificationBanner
        notification={bannerNotification}
        onAcknowledge={acknowledgeNotification}
      />
      <nav style={styles.navbar}>
        <div style={styles.logoContainer}>
          <div style={styles.logoGlow}></div>
          <span style={styles.logoText}>TEIS</span>
          <span style={styles.logoSub}>Trading Edge</span>
        </div>

        <div style={styles.navLinks}>
          <Link
            to="/dashboard"
            style={location.pathname === "/dashboard" || location.pathname === "/" ? styles.activeLink : styles.link}
          >
            Dasbor
          </Link>
          <Link
            to="/journal"
            style={location.pathname === "/journal" ? styles.activeLink : styles.link}
          >
            Daftar Jurnal
          </Link>
          <Link
            to="/quick-tag"
            style={location.pathname === "/quick-tag" ? styles.activeLink : styles.link}
          >
            Quick-Tag
          </Link>
          <Link
            to="/import"
            style={location.pathname === "/import" ? styles.activeLink : styles.link}
          >
            Import Historis
          </Link>
          <Link
            to="/settings"
            style={location.pathname === "/settings" ? styles.activeLink : styles.link}
          >
            Settings
          </Link>
        </div>

        <div style={styles.rightSection}>
          <NotificationBell
            notifications={notifications}
            unreadCount={unreadCount}
            onAcknowledge={acknowledgeNotification}
            onAcknowledgeAll={acknowledgeAllNotifications}
          />

          <button onClick={handleLogout} style={styles.logoutButton}>
            Keluar
          </button>
        </div>
      </nav>
    </>
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
