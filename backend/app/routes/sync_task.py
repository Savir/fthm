import asyncio
import json
from typing import Type, Iterable

import sqlalchemy as sa
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
    """
    Return the most recent sync tasks created by the logged in user ('user' param)
    deduplicated by meeting_id/status. Meaning: if we have two sync tasks for a given
    meeting both with the same status, it will return only the most recent one.
    """
    subq = (
        db.query(
            SyncTask.id,
            sa.func.row_number()
            .over(
                partition_by=[SyncTask.meeting_id, SyncTask.status],
                order_by=SyncTask.updated_at.desc(),
            )
            .label("row_num"),
        )
        .filter(SyncTask.user_id == user["username"])
        .subquery()
    )
    latest_entries: Iterable[Type[SyncTask]]
    latest_entries = (
        db.query(SyncTask).join(subq, SyncTask.id == subq.c.id).filter(subq.c.row_num == 1)
    )
    return [
        {"task_id": st.id, "meeting_id": st.meeting_id, "status": st.status}
        for st in latest_entries
    ]


@router.post("/sync/{meeting_id}/start")
async def start_sync_task(
    meeting_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Start a new sync task for the meeting with ID 'meeting_id' as long as we don't have
    one in progress already.
    Remember: We just care about the finished statuses: ["completed", "failed"]. Any other
    status will be considered "in progress". This allows for a bit more flexibility and
    fine grain control. For instance: the frontend might want to show the actual status
    (jobA, jobB...) or just "syncing..."

    Also note that we allow multiple Synchronization Jobs for the same meeting, as long
    as there isn't one currently "in progress" (not finished). We could easily change this
    to allow re-scheduling only for failed synchronization jobs, but for testing purposes,
    let's allow multiple re-syncs as long as the previous ones are all definitively finished.
    """
    if not user["permissions"]["can_manually_sync"]:
        # 403: I know who you are, but you just can't do this... Dave https://youtu.be/5lsExRvJTAI
        # This should never happen, because we embed permissions in the token and the
        # frontend should hide the sync button. BuuUUUUuuuut... We never, NEVER, ever trust
        # the frontend. EVER
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"User {user['username']} can't manually sync",
        )

    # If we already have a synchronization task for that meeting that is not "finished",
    # then throw an error. The frontend should prevent this from happening, by disabling
    # the <form> to create a new synchronization buuuUUuut... what did we just say about
    # the frontend? That we never ever trust it? Yeah...
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
        "meeting_id": sync_task.meeting_id,  # Nice to show the meetingID on the list of tasks
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
    # which we're using as a cache. If we have queried the status before, we won't need
    # to go to the database.
    redis_client = util_redis.get_client()
    cache_key = util_redis.task_status_key(task_id)
    if not redis_client.exists(cache_key):
        log.info("Cache miss checking task status. Fetching from DB.", task_id=task_id)
        sync_task = (
            db.query(SyncTask.status)
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
    port starvation. If that happens, we should
    """
    log.info("Opening websocket to track task", task_id=task_id)
    await websocket.accept()
    active_websockets[task_id] = websocket
    try:
        while True:
            await asyncio.sleep(5)  # Keep connection alive
    except WebSocketDisconnect:
        active_websockets.pop(task_id, None)  # Safely (no exception) remove
