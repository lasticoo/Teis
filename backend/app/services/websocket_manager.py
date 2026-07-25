import json
import logging
import asyncio
import redis.asyncio as aioredis
from typing import Dict, List
from fastapi import WebSocket
from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections per user or global broadcast for in-app real-time notifications.
    Uses Redis Pub/Sub to allow worker processes to trigger WebSocket broadcasts in backend FastAPI instance.
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.anonymous_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: str = None):
        await websocket.accept()
        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            logger.info(f"WebSocket connected for user {user_id}")
        else:
            self.anonymous_connections.append(websocket)
            logger.info("WebSocket connected for anonymous client")

    def disconnect(self, websocket: WebSocket, user_id: str = None):
        if user_id and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user {user_id}")
        elif websocket in self.anonymous_connections:
            self.anonymous_connections.remove(websocket)
            logger.info("WebSocket disconnected for anonymous client")

    async def send_personal_json(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message to user {user_id}: {str(e)}")

    async def broadcast_json(self, message: dict):
        for user_id, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast WebSocket message to user {user_id}: {str(e)}")

        for connection in list(self.anonymous_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast WebSocket message to anonymous client: {str(e)}")


ws_manager = ConnectionManager()


async def redis_notification_listener():
    """
    Background listener that subscribes to Redis channel 'teis_notifications'
    and relays published messages to active WebSocket connections.
    """
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
    try:
        r = aioredis.from_url(redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("teis_notifications")
        logger.info("📡 Redis Pub/Sub listener connected to 'teis_notifications' channel.")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"].decode("utf-8"))
                    target_user = data.get("user_id")
                    if target_user:
                        await ws_manager.send_personal_json(data, target_user)
                    else:
                        await ws_manager.broadcast_json(data)
                except Exception as ex:
                    logger.error(f"Error handling Redis Pub/Sub notification message: {str(ex)}")
    except Exception as e:
        logger.error(f"Redis Pub/Sub listener error: {str(e)}")


def publish_notification_to_redis(payload: dict):
    """
    Helper for Celery tasks or sync functions to publish a notification to Redis Pub/Sub.
    """
    try:
        import redis as sync_redis
        r = sync_redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        r.publish("teis_notifications", json.dumps(payload))
        logger.info("Published notification payload to Redis channel 'teis_notifications'")
    except Exception as e:
        logger.error(f"Failed to publish notification to Redis: {str(e)}")
