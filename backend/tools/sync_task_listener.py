import asyncio
import json
import logging

import async_timeout
import redis.asyncio as redis
import structlog
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from app.database import ctx_db
from app.models import SyncTask
from tools import constants

redis_client = redis.StrictRedis.from_url(constants.redis_url, decode_responses=True)
log = structlog.get_logger()

active_websockets: dict[int, WebSocket] = {}


async def _update(task_id: int, status: str):
    log.info(f"Received status update for task", task_id=task_id, status=status)

    # Update DB:
    with ctx_db() as db:
        db.query(SyncTask).filter(SyncTask.id == task_id).update({SyncTask.status: status})
        db.commit()
    # Update redis cache
    redis_client.set(str(task_id), status)

    # Push to websockets
    try:
        if websocket := active_websockets.get(task_id, None):
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"task_id": task_id, "status": status})

            if status in constants.completed_statuses:
                del active_websockets[task_id]
    except WebSocketDisconnect:
        log.warning(f"WebSocket disconnected for sync task", sync_task_id=task_id)
    except Exception as e:
        log.exception("Exception updating status via websocket", sync_task_id=task_id)


async def handle_notification():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("task_updates")  # Subscribe to the Redis Pub/Sub channel
    while True:
        task_id = None
        try:
            async with async_timeout.timeout(1):
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    log.info(f"Received message", message=message)
                    data = json.loads(message["data"])
                    task_id = int(data["task_id"])
                    await _update(task_id, data["status"])
                # endif
                await asyncio.sleep(0.5)
        except (asyncio.TimeoutError, json.decoder.JSONDecodeError) as e:
            logging.error(e)
        except Exception:
            log.exception("Exception handling notifications", sync_task_id=task_id)
