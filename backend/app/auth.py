import os
from datetime import datetime, timedelta
import copy
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1

# Temporary user store
users_db = {
    "hector": {
        "username": "hector",
        "password": "hector",
        "permissions": {"can_manually_sync": True},
    },
    "foo": {"username": "foo", "password": "foo", "permissions": {"can_manually_sync": False}},
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def _create_access_token(user: dict, expires_delta: timedelta = None):
    """Generate a short-lived access token."""
    user = copy.deepcopy(user)  # Just in case
    exp = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    jwt_data = {
        "sub": user["username"],
        "permissions": user["permissions"],
        "exp": exp,
    }
    return jwt.encode(jwt_data, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login user and return access token."""
    user = users_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    access_token = _create_access_token(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decode token and return user info."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = users_db[payload["sub"]]
        user = copy.deepcopy(user)
        user.pop("password", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
