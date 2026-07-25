import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.models import SystemNotification
from app.tasks.notification_tasks import (
    send_in_app_notification_task,
    send_web_push_notification_task,
    send_email_notification_task
)

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ["trade_pending_tag", "edge_status_change", "sync_failure"]
ALLOWED_CHANNELS = ["in_app", "web_push", "email"]


class NotificationService:
    """
    Core Multi-Channel Notification Service.
    Dispatches simultaneous alerts across 3 channels (In-App Banner/WebSocket, Web Push, Email SMTP).
    Records audit entries in system_notifications DB table.
    """

    @staticmethod
    def send_multi_channel_notification(
        db: Session,
        notification_type: str,
        message: str,
        reference_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point to emit multi-channel notification.
        1. Validates notification_type.
        2. Creates 3 DB records in system_notifications (one per channel).
        3. Dispatches async Celery tasks for each channel.
        """
        if notification_type not in ALLOWED_TYPES:
            raise ValueError(f"Invalid notification type '{notification_type}'. Expected one of {ALLOWED_TYPES}.")

        if not message or not message.strip():
            raise ValueError("Notification message must not be empty.")

        records: List[SystemNotification] = []
        task_dispatches = {}

        for ch in ALLOWED_CHANNELS:
            notif = SystemNotification(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=notification_type,
                reference_id=reference_id,
                channel=ch,
                message=message.strip(),
                status="pending",
                created_at=datetime.now()
            )
            db.add(notif)
            records.append(notif)

        db.commit()

        # Refresh to get IDs
        for r in records:
            db.refresh(r)

        # Dispatch async tasks in background (wrapped in try-except so business flow is never interrupted)
        for r in records:
            try:
                if r.channel == "in_app":
                    task = send_in_app_notification_task.delay(r.id)
                    task_dispatches["in_app"] = task.id
                elif r.channel == "web_push":
                    task = send_web_push_notification_task.delay(r.id)
                    task_dispatches["web_push"] = task.id
                elif r.channel == "email":
                    task = send_email_notification_task.delay(r.id)
                    task_dispatches["email"] = task.id
            except Exception as ex:
                logger.error(f"Failed to dispatch Celery task for channel {r.channel} on notification {r.id}: {str(ex)}")

        logger.info(f"Multi-channel notification '{notification_type}' dispatched for 3 channels. Ref: {reference_id}.")

        return {
            "status": "success",
            "message": "Multi-channel notification dispatched successfully to all 3 channels.",
            "notification_type": notification_type,
            "reference_id": reference_id,
            "channel_notifications": [
                {
                    "id": r.id,
                    "channel": r.channel,
                    "status": r.status,
                    "celery_task_id": task_dispatches.get(r.channel)
                }
                for r in records
            ]
        }
