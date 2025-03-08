import json
from typing import List, Type

import redis
import structlog
from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.kafka import produce_message
from app.models import SyncTask
from tools import constants
from tools.sync_task_listener import active_websockets

router = APIRouter()  # No prefix. Better be inplicit.
redis_client = redis.StrictRedis.from_url(constants.redis_url, decode_responses=True)

log = structlog.get_logger()


@router.get("/sync")
def get_user_syncs(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all meetings and their sync status for the logged-in user."""
    sync_tasks: List[Type[SyncTask]]
    sync_tasks = db.query(SyncTask).filter(SyncTask.user_id == user["username"]).all()
    return [{"id": st.id, "meeting_id": st.meeting_id, "status": st.status} for st in sync_tasks]


@router.post("/sync/{meeting_id}/start")
async def start_sync_task(
    meeting_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Start a new sync task and enqueue JobA."""
    existing_task = (
        db.query(SyncTask)
        .filter(
            SyncTask.meeting_id == meeting_id,
            SyncTask.user_id == user["username"],
            SyncTask.status.notin_(constants.completed_statuses),
        )
        .first()
    )

    if existing_task:
        raise HTTPException(status_code=400, detail="Sync already in progress")

    sync_task = SyncTask(meeting_id=meeting_id, user_id=user["username"], status="in_progress")
    db.add(sync_task)
    db.commit()

    task_data = {
        "task_id": sync_task.id,
        "meeting_id": meeting_id,
        "status": sync_task.status,
        "user_id": user["username"],
    }
    await produce_message(constants.start_topic, json.dumps(task_data))
    return task_data


@router.get("/sync/{sync_task_id}/status")
def get_sync_status(
    sync_task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Get the status of a sync task."""
    redis_key = str(sync_task_id)
    if not redis_client.exists(redis_key):
        log.info("Cache miss checking task status", task_id=sync_task_id)
        sync_task = (
            db.query(SyncTask)
            .filter(SyncTask.id == sync_task_id, SyncTask.user_id == user["username"])
            .first()
        )
        status = sync_task.status if sync_task else constants.not_found
        redis_client.set(redis_key, status)

    status = redis_client.get(redis_key)
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
    """WebSocket route to send live sync status updates from Redis Pub/Sub."""
    await websocket.accept()
    active_websockets[sync_task_id] = websocket
