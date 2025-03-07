from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import jwt
import os

router = APIRouter()

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Simulated database for refresh tokens (use a real DB in production)
tokens_db = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Generate a short-lived access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(username: str):
    """Generate a long-lived refresh token."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    token = jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    tokens_db[username] = token  # Store refresh token
    return token

def verify_access_token(token: str):
    """Decode and verify access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_refresh_token(token: str):
    """Decode and verify refresh token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload["sub"]
        if tokens_db.get(username) != token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login user and return access & refresh tokens."""
    if form_data.username == "user" and form_data.password == "password":
        access_token = create_access_token({"sub": form_data.username})
        refresh_token = create_refresh_token(form_data.username)
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Invalid credentials")

@router.post("/refresh")
def refresh_token(refresh_token: str):
    """Issue new access token using a valid refresh token."""
    username = verify_refresh_token(refresh_token)
    new_access_token = create_access_token({"sub": username})
    return {"access_token": new_access_token}
