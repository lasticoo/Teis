import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();

  const navItems = [
    { path: "/dashboard", label: "Dasbor Utama", icon: "📊" },
    { path: "/quick-tag", label: "Quick-Tag", icon: "🏷️" },
    { path: "/journal", label: "Jurnal Trade", icon: "📘" },
    { path: "/edges", label: "Edge Blueprint", icon: "🎯" },
    { path: "/review", label: "Review Mingguan", icon: "🖼️" },
    { path: "/import", label: "Import Wizard", icon: "📥" },
    { path: "/settings", label: "Pengaturan", icon: "⚙️" },
  ];

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside style={styles.sidebar}>
      {/* Brand Header */}
      <div style={styles.brandContainer}>
        <div style={styles.logoBadge}>TEIS</div>
        <div style={{ minWidth: 0 }}>
          <h2 style={styles.brandTitle}>TEIS System</h2>
          <span style={styles.brandSubtitle}>Trading Edge Intelligence</span>
        </div>
      </div>

      {/* Navigation List */}
      <nav style={styles.navContainer}>
        {navItems.map((item) => {
          const isActive =
            location.pathname === item.path ||
            (item.path !== "/dashboard" && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                ...styles.navLink,
                ...(isActive ? styles.navLinkActive : {}),
              }}
            >
              <span style={styles.navIcon}>{item.icon}</span>
              <span style={styles.navLabel}>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User Footer / Logout */}
      <div style={styles.footerContainer}>
        <div style={styles.userInfo}>
          <div style={styles.avatar}>T</div>
          <div style={{ overflow: "hidden" }}>
            <div style={styles.userName}>Trader Pro</div>
            <div style={styles.userRole}>Authenticated</div>
          </div>
        </div>
        <button onClick={handleLogout} style={styles.logoutBtn} title="Keluar dari Aplikasi">
          🚪
        </button>
      </div>
    </aside>
  );
};

const styles = {
  sidebar: {
    width: "230px",
    backgroundColor: "#0d0e12",
    borderRight: "1px solid #1e2329",
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    position: "sticky",
    top: 0,
    zIndex: 100,
    userSelect: "none",
    boxShadow: "2px 0 10px rgba(0, 0, 0, 0.3)"
  },
  brandContainer: {
    padding: "18px 16px",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    borderBottom: "1px solid #1e2329"
  },
  logoBadge: {
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    fontWeight: "900",
    fontSize: "12px",
    padding: "6px 8px",
    borderRadius: "8px",
    letterSpacing: "1px",
    boxShadow: "0 2px 8px rgba(124, 58, 237, 0.4)"
  },
  brandTitle: {
    margin: 0,
    fontSize: "14px",
    fontWeight: "800",
    color: "#f8fafc",
    letterSpacing: "0.5px"
  },
  brandSubtitle: {
    fontSize: "10.5px",
    color: "#64748b"
  },
  navContainer: {
    padding: "12px 10px",
    display: "flex",
    flexDirection: "column",
    gap: "3px",
    flex: 1,
    overflowY: "auto"
  },
  navLink: {
    display: "flex",
    alignItems: "center",
    padding: "10px 12px",
    borderRadius: "8px",
    color: "#94a3b8",
    textDecoration: "none",
    fontSize: "13px",
    fontWeight: "500",
    transition: "all 0.2s ease"
  },
  navLinkActive: {
    backgroundColor: "rgba(124, 58, 237, 0.18)",
    color: "#c4b5fd",
    fontWeight: "700",
    borderLeft: "3px solid #8b5cf6"
  },
  navIcon: {
    fontSize: "15px",
    marginRight: "10px"
  },
  navLabel: {
    flex: 1
  },
  footerContainer: {
    padding: "14px 16px",
    borderTop: "1px solid #1e2329",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#090a0f"
  },
  userInfo: {
    display: "flex",
    alignItems: "center",
    gap: "10px"
  },
  avatar: {
    width: "30px",
    height: "30px",
    borderRadius: "50%",
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: "800",
    fontSize: "13px"
  },
  userName: {
    fontSize: "12.5px",
    fontWeight: "700",
    color: "#f1f5f9"
  },
  userRole: {
    fontSize: "10px",
    color: "#22c55e",
    fontWeight: "600"
  },
  logoutBtn: {
    backgroundColor: "transparent",
    border: "none",
    color: "#94a3b8",
    fontSize: "15px",
    cursor: "pointer",
    padding: "6px",
    borderRadius: "6px",
    transition: "background 0.2s ease"
  }
};

export default Sidebar;
