import React from "react";
import { useNavigate } from "react-router-dom";

const NotificationBanner = ({ notification, onAcknowledge }) => {
  const navigate = useNavigate();

  if (!notification) return null;

  const isPendingTag = notification.type === "trade_pending_tag";
  const isEdgeChange = notification.type === "edge_status_change";

  const bannerStyle = {
    backgroundColor: isPendingTag
      ? "rgba(245, 158, 11, 0.95)"
      : isEdgeChange
      ? "rgba(239, 68, 68, 0.95)"
      : "rgba(59, 130, 246, 0.95)",
    color: "#ffffff",
    padding: "10px 20px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "13px",
    fontWeight: "600",
    boxShadow: "0 4px 15px rgba(0,0,0,0.3)",
    backdropFilter: "blur(10px)",
    zIndex: 9999,
    position: "relative",
    animation: "fadeIn 0.3s ease-in-out",
  };

  const btnStyle = {
    backgroundColor: "#ffffff",
    color: isPendingTag ? "#d97706" : isEdgeChange ? "#dc2626" : "#2563eb",
    border: "none",
    padding: "5px 12px",
    borderRadius: "6px",
    fontWeight: "700",
    fontSize: "12px",
    cursor: "pointer",
    marginLeft: "12px",
    transition: "transform 0.15s ease",
  };

  const closeBtnStyle = {
    background: "none",
    border: "none",
    color: "#ffffff",
    fontSize: "16px",
    cursor: "pointer",
    marginLeft: "12px",
    opacity: 0.8,
  };

  const handleAction = () => {
    if (notification.reference_id && isPendingTag) {
      navigate(`/journal/detail/${notification.reference_id}`);
    } else {
      navigate("/journal");
    }
    if (onAcknowledge) onAcknowledge(notification.id);
  };

  return (
    <div style={bannerStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{ fontSize: "16px" }}>
          {isPendingTag ? "⚡" : isEdgeChange ? "📉" : "ℹ️"}
        </span>
        <span>{notification.message}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        <button
          onClick={handleAction}
          style={btnStyle}
          onMouseOver={(e) => (e.currentTarget.style.transform = "scale(1.05)")}
          onMouseOut={(e) => (e.currentTarget.style.transform = "scale(1)")}
        >
          {isPendingTag ? "🏷️ Lakukan Quick-Tag" : "Lihat Detail"}
        </button>
        <button
          onClick={() => onAcknowledge && onAcknowledge(notification.id)}
          style={closeBtnStyle}
          title="Tutup Notifikasi"
        >
          ✕
        </button>
      </div>
    </div>
  );
};

export default NotificationBanner;
