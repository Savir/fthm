from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class SyncStatus(Base):
    __tablename__ = "sync_status"
    id = Column(Integer, primary_key=True, index=True)
    # meeting_id = Column(String, unique=True, index=True)
    # status = Column(String, default="pending")  # pending, in_progress, success, failure
    # last_updated = Column(DateTime, default=datetime.utcnow)
