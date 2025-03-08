import os
import typing
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

if typing.TYPE_CHECKING:
    from sqlalchemy.orm import Session
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@db:3306/fthm")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def ctx_db() -> "Session":
    """Context manager for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db() -> "Session":
    """Generator for FastAPI dependency, reusing ctx_db()."""
    with ctx_db() as db:
        yield db
