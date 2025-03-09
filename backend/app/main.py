import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_routes
from tools.database import engine, Base
from app.routes import sync_task_router
from tools.sync_task_listener import status_updates_listener

log = structlog.get_logger()

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(sync_task_router)
app.include_router(auth_routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Only allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.get("/")
def read_root():
    return {"message": "Backend is running"}


@app.on_event("startup")
async def startup_event():
    """Runs when the FastAPI server starts."""
    log.info("Starting the FastAPI server")
    asyncio.create_task(status_updates_listener())
