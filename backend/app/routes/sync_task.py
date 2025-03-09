import asyncio
import json
from typing import Type, Iterable

import structlog
from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi import WebSocket
from fastapi import status as http_status
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models import SyncTask
from app.routes.auth import get_current_user
from tools import constants, util_redis
from tools.database import get_db
from tools.kafka import produce_message
from .sync_task_websocket import active_websockets

router = APIRouter()  # No prefix. Better be implicit on each route.

log = structlog.get_logger()


@router.get("/sync")
def get_user_syncs(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all meetings and their sync status for the logged-in user."""
    sync_tasks: Iterable[Type[SyncTask]]
    sync_tasks = db.query(SyncTask).filter(SyncTask.user_id == user["username"])
    return [{"id": st.id, "meeting_id": st.meeting_id, "status": st.status} for st in sync_tasks]


@router.post("/sync/{meeting_id}/start")
async def start_sync_task(
    meeting_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Start a new sync task for the meeting with ID 'meeting_id'"""
    if not user["permissions"]["can_manually_sync"]:
        # 403: I know who you are, but you just can't do this... Dave https://youtu.be/5lsExRvJTAI
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"User {user['username']} can't manually sync",
        )

    # If we already have a synchronization task for that meeting that is not "finished",
    # then throw an error.
    existing_task = db.query(
        db.query(SyncTask)
        .filter(
            SyncTask.meeting_id == meeting_id,
            SyncTask.user_id == user["username"],
            SyncTask.status.notin_(constants.finished_statuses),
        )
        .exists()
    ).scalar()

    if existing_task:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Sync for meeting {meeting_id} already in progress",
        )

    # Ok: If we're here, we can create a new synchronization task and send it to the Kafka
    #     worker for processing.
    sync_task = SyncTask(meeting_id=meeting_id, user_id=user["username"])
    db.add(sync_task)
    db.commit()

    task_data = {
        "task_id": sync_task.id,
        "meeting_id": sync_task.meeting_id,
        "user_id": sync_task.user_id,
        "status": sync_task.status,
    }
    log.info("Meeting synchronization task started", **task_data)
    await produce_message(constants.start_topic, json.dumps(task_data))
    return task_data


@router.get("/sync/{task_id}/status")
def get_sync_status(
    task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    """
    Get the status of a sync task using "regular" periodic polling in the frontend.
    We should rarely use this, since we have websockets, but just in case.
    """

    # First, query the best thing ever invented by mankind since chocolate milk (Redis)
    # which we're using as a cache.
    redis_client = util_redis.get_client()
    cache_key = util_redis.task_status_key(task_id)
    if not redis_client.exists(cache_key):
        log.info("Cache miss checking task status. Fetching from DB.", task_id=task_id)
        sync_task = (
            db.query(SyncTask)
            .filter(SyncTask.id == task_id, SyncTask.user_id == user["username"])
            .first()
        )
        # Even if the sync task was not found in the database, set a status in the
        # Cache to ensure non-existing tasks don't pound our database
        status = sync_task.status if sync_task else constants.not_found
        redis_client.set(cache_key, status)

    status = redis_client.get(cache_key)
    if status == constants.not_found:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No sync task found with id {task_id}",
        )

    task_data = {
        "task_id": task_id,
        "status": status,
    }
    return task_data


@router.websocket("/ws/sync/{task_id}/status")
async def sync_status_ws(websocket: WebSocket, task_id: int):
    """
    Route our frontend can call to open a WebSocket.
    This websocket will be used to push live sync status updates for the synchronization
    task with ID task_id to the frontend.
    Notice each task will have its own WebSocket. This could (potentially) lead to
    port starvation.
    """
    log.info("Opening websocket to track task", task_id=task_id)
    await websocket.accept()
    active_websockets[task_id] = websocket
    try:
        while True:
            await asyncio.sleep(5)  # Keep connection alive
    except WebSocketDisconnect:
        active_websockets.pop(task_id, None)  # Safely (no exception) remove
