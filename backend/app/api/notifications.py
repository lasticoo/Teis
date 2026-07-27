import logging
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import SystemNotification, WebPushSubscription, User
from app.services.notification_service import NotificationService
from app.services.websocket_manager import ws_manager
from app.services.vapid_helper import get_vapid_keys

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])


# Pydantic Schemas
class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


class TestNotificationRequest(BaseModel):
    type: str  # trade_pending_tag, edge_status_change, sync_failure
    message: str
    reference_id: Optional[str] = None


@router.get("/notifications")
def get_in_app_notifications(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Returns active unacknowledged in-app notifications for bell dropdown & banner.
    """
    query = db.query(SystemNotification).filter(
        SystemNotification.channel == "in_app",
        SystemNotification.acknowledged_at == None
    )
    notifications = query.order_by(SystemNotification.sent_at.desc()).limit(20).all()

    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "reference_id": n.reference_id,
                "message": n.message,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "url": f"/journal/detail/{n.reference_id}" if n.reference_id and n.type == "trade_pending_tag" else "/journal"
            }
            for n in notifications
        ],
        "unread_count": len(notifications)
    }


@router.post("/notifications/acknowledge/{notification_id}")
def acknowledge_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marks a single notification as acknowledged (read).
    """
    notif = db.query(SystemNotification).filter(SystemNotification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notif.acknowledged_at = datetime.now()
    db.commit()
    return {"status": "success", "message": "Notification acknowledged."}


@router.post("/notifications/acknowledge-all")
def acknowledge_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marks all unacknowledged in-app notifications for user as acknowledged.
    """
    db.query(SystemNotification).filter(
        SystemNotification.channel == "in_app",
        SystemNotification.acknowledged_at == None
    ).update({"acknowledged_at": datetime.now()}, synchronize_session=False)

    db.commit()
    return {"status": "success", "message": "All notifications marked as acknowledged."}


@router.get("/notifications/vapid-public-key")
def get_vapid_public_key():
    """
    Returns the VAPID Public Key required by browser ServiceWorker to subscribe to WebPush.
    """
    pub_key, _ = get_vapid_keys()
    return {"public_key": pub_key}


@router.post("/notifications/subscribe-push")
def subscribe_web_push(
    request: PushSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Saves or updates browser WebPush subscription credentials (endpoint, p256dh, auth).
    """
    p256dh = request.keys.get("p256dh", "")
    auth = request.keys.get("auth", "")

    if not request.endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid push subscription payload.")

    sub = db.query(WebPushSubscription).filter(
        WebPushSubscription.user_id == current_user.id,
        WebPushSubscription.endpoint == request.endpoint
    ).first()

    if not sub:
        sub = WebPushSubscription(
            user_id=current_user.id,
            endpoint=request.endpoint,
            p256dh=p256dh,
            auth=auth,
            created_at=datetime.now()
        )
        db.add(sub)
    else:
        sub.p256dh = p256dh
        sub.auth = auth

    db.commit()
    logger.info(f"Saved WebPush subscription for user {current_user.id}.")
    return {"status": "success", "message": "WebPush subscription registered successfully."}


@router.post("/notifications/trigger-test")
def trigger_test_notification(
    request: TestNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Simulation endpoint to test multi-channel notification dispatch.
    Emits alerts across In-App Banner (WebSocket), Web Push, and Email SMTP simultaneously.
    """
    result = NotificationService.send_multi_channel_notification(
        db=db,
        notification_type=request.type,
        message=request.message,
        reference_id=request.reference_id,
        user_id=current_user.id
    )
    return result


@router.websocket("/notifications/ws")
async def websocket_notifications_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time in-app notification banner & alerts.
    """
    user_id = None
    if token:
        try:
            import jwt
            from app.config import settings
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
        except Exception:
            pass

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive & listen for client ping/messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        ws_manager.disconnect(websocket, user_id)
