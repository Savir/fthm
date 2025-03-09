import asyncio
import json
from typing import Type, Iterable

import redis
import structlog
from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi import WebSocket
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.auth import get_current_user
from app.models import SyncTask
from tools import constants, util_redis
from tools.database import get_db
from tools.kafka import produce_message
from tools.sync_task_listener import active_websockets

router = APIRouter()  # No prefix. Better be implicit on each route.
redis_client = redis.StrictRedis.from_url(constants.redis_url, decode_responses=True)

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
        raise HTTPException(status_code=403, detail=f"User {user['username']} can't manually sync")

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
            status_code=400, detail=f"Sync for meeting {meeting_id} already in progress"
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


@router.get("/sync/{sync_task_id}/status")
def get_sync_status(
    sync_task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Get the status of a sync task."""
    cache_key = util_redis.task_status_key(sync_task_id)
    if not redis_client.exists(cache_key):
        log.info("Cache miss checking task status. Fetching from DB.", task_id=sync_task_id)
        sync_task = (
            db.query(SyncTask)
            .filter(SyncTask.id == sync_task_id, SyncTask.user_id == user["username"])
            .first()
        )
        status = sync_task.status if sync_task else constants.not_found
        redis_client.set(cache_key, status)

    status = redis_client.get(cache_key)
    if status == constants.not_found:
        raise HTTPException(status_code=404, detail=f"No sync task found with id {sync_task_id}")
    task_data = {
        "task_id": sync_task_id,
        "status": status,
        "user_id": user["username"],
    }
    return task_data


@router.websocket("/ws/sync/{sync_task_id}/status")
async def sync_status_ws(websocket: WebSocket, sync_task_id: int):
    """WebSocket route to send live sync status updates."""
    await websocket.accept()
    active_websockets[sync_task_id] = websocket
    try:
        while True:
            await asyncio.sleep(10)  # Keep connection alive
    except WebSocketDisconnect:
        del active_websockets[sync_task_id]
