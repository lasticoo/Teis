import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const NotificationBell = ({ notifications = [], unreadCount = 0, onAcknowledge, onAcknowledgeAll }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleItemClick = (notif) => {
    if (onAcknowledge) onAcknowledge(notif.id);
    setIsOpen(false);
    if (notif.reference_id && notif.type === "trade_pending_tag") {
      navigate(`/journal/detail/${notif.reference_id}`);
    } else {
      navigate("/journal");
    }
  };

  const bellContainerStyle = {
    position: "relative",
    display: "inline-block",
  };

  const bellBtnStyle = {
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: "10px",
    color: "#e2e8f0",
    padding: "8px 12px",
    fontSize: "16px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.2s ease",
  };

  const badgeStyle = {
    position: "absolute",
    top: "-4px",
    right: "-4px",
    backgroundColor: "#ef4444",
    color: "#ffffff",
    borderRadius: "10px",
    padding: "2px 6px",
    fontSize: "10px",
    fontWeight: "800",
    border: "2px solid #0f0c1e",
    boxShadow: "0 0 10px rgba(239, 68, 68, 0.6)",
  };

  const dropdownStyle = {
    position: "absolute",
    top: "45px",
    right: 0,
    width: "320px",
    backgroundColor: "rgba(22, 19, 39, 0.96)",
    border: "1px solid rgba(255, 255, 255, 0.12)",
    borderRadius: "12px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.6)",
    backdropFilter: "blur(12px)",
    zIndex: 9999,
    overflow: "hidden",
  };

  const headerStyle = {
    padding: "12px 16px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  };

  const ackAllBtnStyle = {
    background: "none",
    border: "none",
    color: "#7c3aed",
    fontSize: "11px",
    fontWeight: "700",
    cursor: "pointer",
  };

  const listStyle = {
    maxHeight: "300px",
    overflowY: "auto",
  };

  const itemStyle = {
    padding: "12px 16px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
    cursor: "pointer",
    transition: "background-color 0.15s ease",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  };

  return (
    <div style={bellContainerStyle} ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={bellBtnStyle}
        title="Notifikasi Sistem"
      >
        🔔
        {unreadCount > 0 && <span style={badgeStyle}>{unreadCount}</span>}
      </button>

      {isOpen && (
        <div style={dropdownStyle}>
          <div style={headerStyle}>
            <span style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc" }}>
              🔔 Notifikasi TEIS
            </span>
            {unreadCount > 0 && (
              <button onClick={() => onAcknowledgeAll && onAcknowledgeAll()} style={ackAllBtnStyle}>
                Tandai Semua Dibaca
              </button>
            )}
          </div>

          <div style={listStyle}>
            {notifications.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", fontSize: "12px", color: "#64748b" }}>
                Tidak ada notifikasi baru.
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  style={itemStyle}
                  onClick={() => handleItemClick(n)}
                  onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)")}
                  onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "11px", fontWeight: "700", color: "#a78bfa" }}>
                      {n.type === "trade_pending_tag" ? "⚡ Trade Pending Tag" : n.type === "edge_status_change" ? "📉 Status Edge" : "⚠️ System Alert"}
                    </span>
                    <span style={{ fontSize: "10px", color: "#64748b" }}>
                      {n.created_at ? new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}
                    </span>
                  </div>
                  <span style={{ fontSize: "12px", color: "#e2e8f0", lineHeight: "1.4" }}>
                    {n.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
