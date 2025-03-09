import asyncio
import json
import logging

import structlog
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from tools import constants
from tools.kafka import consume_messages

log = structlog.get_logger()

active_websockets: dict[int, WebSocket] = {}  # SyncTask.ID to Websocket


async def _push_task_status(task_id: int, status: str):
    """
    Push a new status to the tasks's active websocket (if the websocket exists and it's active)
    """

    # Push to WebSocket if active
    websocket = active_websockets.get(task_id)
    if websocket and websocket.client_state == WebSocketState.CONNECTED:
        try:
            log.info(f"Pushing status update for task via websocket", task_id=task_id, status=status)
            await websocket.send_json({"task_id": task_id, "status": status})
        except WebSocketDisconnect:
            log.warning(f"WebSocket disconnected for sync task", task_id=task_id)
            active_websockets.pop(task_id, None)
        except Exception:
            log.exception("Exception updating status via websocket", task_id=task_id)


async def status_updates_listener():
    """
    Our task processor or "worker machine" pushes status changes into a specific topic.
    This function listen for those changes and push them to the frontend.
    The (sort-of) background task will be (or should be) started in FastAPI's main.py in a
    on_event("startup") to ensure it's running when the server boots.
    """
    async for message in consume_messages(constants.status_updates_topic):
        task_id = None
        try:
            data = json.loads(message)
            task_id = int(data["task_id"])  # Just in case... ensure it's an int
            await _push_task_status(task_id, data["status"])
        except (asyncio.TimeoutError, json.decoder.JSONDecodeError) as e:
            logging.exception(e)
        except Exception:
            log.exception("Exception handling notifications", sync_task_id=task_id)
