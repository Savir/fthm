from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import SyncStatus

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/sync/status/{meeting_id}")
def get_sync_status(meeting_id: str, db: Session = Depends(get_db)):
    sync = db.query(SyncStatus).filter(SyncStatus.meeting_id == meeting_id).first()
    if not sync:
        return {"meeting_id": meeting_id, "status": "not_found"}
    return {"meeting_id": sync.meeting_id, "status": sync.status, "last_updated": sync.last_updated}
