from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects import mysql

from tools.database import Base


class SyncTask(Base):
    __tablename__ = "sync_tasks"

    id = Column(mysql.BIGINT(unsigned=True), primary_key=True, index=True)
    user_id = Column(String(128), index=True)  # Track user who started it
    meeting_id = Column(mysql.BIGINT(unsigned=True), index=True)
    status = Column(String(128), default="in_progress")  # in_progress, failed, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

