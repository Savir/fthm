import asyncio
import json
from typing import List, Type

import redis
from fastapi import APIRouter
from fastapi import Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app import constants
from app.auth import get_current_user
from app.database import SessionLocal
from app.kafka import produce_message
from app.models import SyncTask

# Redis Configuration
REDIS_URL = "redis://redis:6379"
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

router = APIRouter()  # No prefix. Better be inplicit.


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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

    task_data = {"task_id": sync_task.id, "meeting_id": meeting_id, "user_id": user["username"]}
    await produce_message(constants.start_topic, json.dumps(task_data))

    return task_data


@router.get("/sync/{sync_task_id}/status")
def get_sync_status(
    sync_task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Get the status of a sync task."""
    sync_task = (
        db.query(SyncTask)
        .filter(SyncTask.id == sync_task_id, SyncTask.user_id == user["username"])
        .one()
    )
    if not sync_task:
        raise HTTPException(status_code=404, detail="No sync task found")
    task_data = {"task_id": sync_task.id, "meeting_id": sync_task.meeting_id, "user_id": user["username"]}
    return task_data


active_connections = {}


@router.websocket("/ws/sync/{sync_task_id}/status")
async def sync_status_ws(websocket: WebSocket, sync_task_id: int):
    """WebSocket route to send live sync status updates from Redis Pub/Sub."""
    await websocket.accept()
    active_connections[sync_task_id] = websocket

    pubsub = redis_client.pubsub()
    pubsub.subscribe("task_updates")  # Subscribe to the Redis Pub/Sub channel

    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = json.loads(message["data"])
                task_id = int(data["task_id"])
                status = data["status"]

                # Send update ONLY if it matches the requested task ID
                if task_id == sync_task_id:
                    await websocket.send_json({"sync_task_id": task_id, "status": status})

            await asyncio.sleep(0.1)  # Prevent high CPU usage
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for sync task {sync_task_id}")
    finally:
        del active_connections[sync_task_id]
