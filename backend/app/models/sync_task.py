from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class SyncTask(Base):
    __tablename__ = "sync_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), index=True)  # Track user who started it
    meeting_id = Column(String(128), unique=True, index=True)
    status = Column(String(128), default="in_progress")  # in_progress, failed, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

