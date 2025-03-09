import asyncio
import json
import logging

import redis.asyncio as redis
import structlog
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from tools import constants
from tools.kafka import consume_messages

redis_client = redis.StrictRedis.from_url(constants.redis_url, decode_responses=True)
log = structlog.get_logger()

active_websockets: dict[int, WebSocket] = {}


async def _update_task_status(task_id: int, status: str):
    log.info(f"Received status update for task", task_id=task_id, status=status)
    # Push to WebSocket if active
    websocket = active_websockets.get(task_id)
    if websocket and websocket.client_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_json({"task_id": task_id, "status": status})
        except WebSocketDisconnect:
            log.warning(f"WebSocket disconnected for sync task", sync_task_id=task_id)
            active_websockets.pop(task_id, None)
        except Exception:
            log.exception("Exception updating status via websocket", sync_task_id=task_id)

    if websocket and websocket.client_state != WebSocketState.CONNECTED:
        active_websockets.pop(task_id, None)


async def status_updates_listener():
    async for message in consume_messages(constants.status_updates_topic):
        task_id = None
        try:
            log.info(f"Received status_update message", message=message)
            data = json.loads(message)
            task_id = int(data["task_id"])
            await _update_task_status(task_id, data["status"])
        except (asyncio.TimeoutError, json.decoder.JSONDecodeError) as e:
            logging.error(e)
        except Exception:
            log.exception("Exception handling notifications", sync_task_id=task_id)
