import React, { useEffect, useState, useCallback } from "react";
import { useLocation } from "react-router-dom";
import NotificationBanner from "./NotificationBanner";
import NotificationBell from "./NotificationBell";

export default function TopHeader() {
  const location = useLocation();

  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [bannerNotification, setBannerNotification] = useState(null);

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  const triggerBrowserPush = (notif) => {
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification("⚡ TEIS V1.3 Notification", {
          body: notif.message,
          dir: "auto",
        });
      } catch (e) {
        console.error("Browser push error", e);
      }
    }
  };

  const fetchNotifications = useCallback(async () => {
    try {
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      if (!token) return;

      const res = await fetch("http://localhost:8000/api/v1/notifications", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const fetchedNotifs = data.notifications || [];
        setNotifications(fetchedNotifs);
        setUnreadCount(data.unread_count || 0);

        // Check for new notifications to trigger desktop popup
        if (fetchedNotifs.length > 0) {
          const newest = fetchedNotifs[0];
          const lastNotifId = localStorage.getItem("teis_last_pushed_notif");
          if (lastNotifId !== newest.id) {
            localStorage.setItem("teis_last_pushed_notif", newest.id);
            triggerBrowserPush(newest);
          }
        }

        const pendingTag = fetchedNotifs.find((n) => n.type === "trade_pending_tag");
        if (pendingTag) {
          setBannerNotification(pendingTag);
        } else if (fetchedNotifs.length > 0) {
          setBannerNotification(fetchedNotifs[0]);
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
    const interval = setInterval(fetchNotifications, 3000); // Polling fast 3 seconds
    return () => clearInterval(interval);
  }, [fetchNotifications, location.pathname]);

  return (
    <div style={styles.headerWrapper}>
      {/* Active Notification Banner */}
      <div style={styles.bannerContainer}>
        {bannerNotification && (
          <NotificationBanner
            notification={bannerNotification}
            onAcknowledge={acknowledgeNotification}
          />
        )}
      </div>

      {/* Notification Bell Icon */}
      <div style={styles.bellContainer}>
        <NotificationBell
          notifications={notifications}
          unreadCount={unreadCount}
          onAcknowledge={acknowledgeNotification}
          onAcknowledgeAll={acknowledgeAllNotifications}
        />
      </div>
    </div>
  );
}

const styles = {
  headerWrapper: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 24px",
    backgroundColor: "#0b0e11",
    borderBottom: "1px solid #1e2329",
    minHeight: "48px"
  },
  bannerContainer: {
    flex: 1,
    marginRight: "16px"
  },
  bellContainer: {
    display: "flex",
    alignItems: "center"
  }
};
