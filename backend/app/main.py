from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_routes
from app.database import engine, Base
from app.routes import router as api_router

Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(api_router)
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
