import json
import logging
import smtplib
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app.models.models import SystemNotification, WebPushSubscription, User
from app.services.websocket_manager import ws_manager, publish_notification_to_redis
from app.services.vapid_helper import get_vapid_keys
from app.tasks.worker import celery_app

logger = logging.getLogger(__name__)
WIB_TZ = pytz.timezone("Asia/Jakarta")


@celery_app.task(name="tasks.send_in_app_notification", bind=True, max_retries=3)
def send_in_app_notification_task(self, notification_id: str):
    """
    Celery task to send In-App Notification via Redis Pub/Sub relay to WebSocket manager and update DB status.
    """
    db = SessionLocal()
    try:
        notif = db.query(SystemNotification).filter(SystemNotification.id == notification_id).first()
        if not notif:
            logger.error(f"In-App Notification record {notification_id} not found in DB.")
            return "not_found"

        created_wib = notif.sent_at
        if created_wib and created_wib.tzinfo is None:
            created_wib = pytz.utc.localize(created_wib).astimezone(WIB_TZ)

        payload = {
            "id": notif.id,
            "type": notif.type,
            "reference_id": notif.reference_id,
            "message": notif.message,
            "channel": "in_app",
            "sent_at": created_wib.strftime("%Y-%m-%d %H:%M:%S") + " WIB" if created_wib else datetime.now(WIB_TZ).strftime("%Y-%m-%d %H:%M:%S") + " WIB"
        }

        # Relay to Redis Pub/Sub so FastAPI WebSocket manager broadcasts it to browser
        publish_notification_to_redis(payload)

        notif.sent_at = datetime.now()
        db.commit()
        logger.info(f"In-App WebSocket notification {notification_id} dispatched successfully via Redis Pub/Sub.")
        return "sent"
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error dispatching In-App WebSocket notification {notification_id}: {err_msg}")
        return "failed"
    finally:
        db.close()



@celery_app.task(name="tasks.send_web_push_notification", bind=True, max_retries=2)
def send_web_push_notification_task(self, notification_id: str):
    """
    Celery task to send Web Push notification using pywebpush and VAPID keys.
    """
    db = SessionLocal()
    try:
        notif = db.query(SystemNotification).filter(SystemNotification.id == notification_id).first()
        if not notif:
            logger.error(f"WebPush Notification record {notification_id} not found in DB.")
            return "not_found"

        # Query subscriptions
        subscriptions = db.query(WebPushSubscription).all()

        if not subscriptions:
            msg = "No WebPush subscriptions found."
            logger.info(msg)
            return "no_subscriptions"

        vapid_pub, vapid_priv = get_vapid_keys()

        payload_dict = {
            "title": "TEIS Notification",
            "body": notif.message,
            "type": notif.type,
            "reference_id": notif.reference_id,
            "id": notif.id,
            "url": f"/journal/detail/{notif.reference_id}" if notif.reference_id and notif.type == "trade_pending_tag" else "/journal"
        }
        payload_json = json.dumps(payload_dict)

        success_count = 0
        errors = []

        try:
            from pywebpush import webpush, WebPushException
            for sub in subscriptions:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                }
                try:
                    webpush(
                        subscription_info=sub_info,
                        data=payload_json,
                        vapid_private_key=vapid_priv,
                        vapid_claims={"sub": f"mailto:{settings.VAPID_ADMIN_EMAIL}"}
                    )
                    success_count += 1
                except WebPushException as ex:
                    logger.warning(f"WebPushException for sub {sub.id}: {str(ex)}")
                    errors.append(str(ex))
        except ImportError:
            msg = "pywebpush package not installed in environment."
            logger.error(msg)
            return "import_error"

        if success_count > 0:
            notif.sent_at = datetime.now()
            logger.info(f"Web Push notification {notification_id} sent successfully to {success_count} device(s).")

        db.commit()
        return "sent" if success_count > 0 else "failed"
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error sending Web Push notification {notification_id}: {err_msg}")
        return "failed"
    finally:
        db.close()


@celery_app.task(name="tasks.send_email_notification", bind=True, max_retries=3, default_retry_delay=10)
def send_email_notification_task(self, notification_id: str):
    """
    Celery task to send Email notification via SMTP relay.
    """
    db = SessionLocal()
    notif = None
    try:
        notif = db.query(SystemNotification).filter(SystemNotification.id == notification_id).first()
        if not notif:
            logger.error(f"Email Notification record {notification_id} not found in DB.")
            return "not_found"

        recipient_email = None
        first_user = db.query(User).filter(User.email != None, User.email != "").first()
        if first_user:
            recipient_email = first_user.email

        if not recipient_email:
            recipient_email = settings.SMTP_FROM_EMAIL

        subject = f"[TEIS Alert] {notif.type.replace('_', ' ').title()}"
        body_text = f"Trading Edge Intelligence System Notification\n\nType: {notif.type}\nMessage: {notif.message}\nReference ID: {notif.reference_id or '—'}\nTime: {datetime.now(WIB_TZ).strftime('%Y-%m-%d %H:%M:%S')} WIB\n\nAccess TEIS Dashboard: http://localhost:5173"

        html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0b0f19; color: #f3f4f6; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #111827; border: 1px solid #1f2937; border-radius: 16px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
  .header {{ text-align: center; border-bottom: 1px solid #1f2937; padding-bottom: 20px; margin-bottom: 25px; }}
  .logo-title {{ font-size: 20px; font-weight: 800; background: linear-gradient(90deg, #a855f7, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 1px; }}
  .alert-badge {{ display: inline-block; background: rgba(234, 179, 8, 0.15); border: 1px solid #eab308; color: #fde047; padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 13px; margin-top: 10px; }}
  .content {{ font-size: 15px; line-height: 1.6; color: #d1d5db; }}
  .trade-box {{ background: #1f2937; border-left: 4px solid #8b5cf6; border-radius: 8px; padding: 18px; margin: 20px 0; color: #f3f4f6; font-size: 15px; }}
  .quote-box {{ background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 18px; margin: 25px 0; text-align: center; font-style: italic; color: #c084fc; }}
  .quote-author {{ font-size: 12px; font-style: normal; font-weight: 700; color: #93c5fd; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }}
  .btn-container {{ text-align: center; margin-top: 30px; }}
  .btn {{ display: inline-block; background: linear-gradient(135deg, #7c3aed, #4f46e5); color: #ffffff !important; text-decoration: none; padding: 14px 28px; border-radius: 10px; font-weight: 700; font-size: 15px; box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4); }}
  .footer {{ text-align: center; font-size: 12px; color: #6b7280; margin-top: 35px; border-top: 1px solid #1f2937; padding-top: 20px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-title">⚡ TRADING EDGE INTELLIGENCE SYSTEM</div>
      <div class="alert-badge">🔔 Notifikasi Trade Binance Sync</div>
    </div>
    <div class="content">
      <p>Halo <strong>Trader</strong>,</p>
      <p>Sistem TEIS telah mendeteksi aktivitas transaksi baru di akun Binance Futures Anda:</p>
      
      <div class="trade-box">
        <strong>Pesan Sistem:</strong><br>
        {notif.message}
      </div>

      <div class="quote-box">
        "Disiplin adalah pembeda utama antara trader amatir dan trader profesional yang konsisten. Satu pencatatan Quick-Tag hari ini menjaga Edge Trading Anda tetap tajam!"
        <div class="quote-author">— TEIS Trading Mindset</div>
      </div>

      <div class="btn-container">
        <a href="http://localhost:5173/quick-tag" class="btn">🏷️ Catat Quick-Tag Sekarang</a>
      </div>
    </div>
    <div class="footer">
      Dibuat secara otomatis oleh Trading Edge Intelligence System (TEIS) • Waktu Server: {datetime.now(WIB_TZ).strftime('%d %B %Y, %H:%M:%S')} WIB
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send via SMTP server (with STARTTLS support for Gmail)
        with smtplib.SMTP(host=settings.SMTP_HOST, port=settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            if settings.SMTP_PORT == 587 or "gmail" in settings.SMTP_HOST.lower():
                server.starttls()
                server.ehlo()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        notif.sent_at = datetime.now()
        db.commit()
        logger.info(f"HTML Email notification {notification_id} sent successfully to {recipient_email}.")
        return "sent"

    except Exception as e:
        err_msg = str(e)
        logger.error(f"SMTP error sending email notification {notification_id}: {err_msg}")
        return "failed"
    finally:
        db.close()
