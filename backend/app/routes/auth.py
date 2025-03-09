import copy
import os
from datetime import datetime, timedelta

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from tools import pw_encryptor

router = APIRouter()
log = structlog.get_logger()


SECRET_KEY = os.getenv("SECRET_KEY", default="mysecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
token_url = "/token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=token_url)

# Temporary user """database table""" (cough, cough). Just for testing!!
users_db = {
    "hector": {
        "username": "hector",
        "password": pw_encryptor.hash_password("hector"),
        "permissions": {"can_manually_sync": True},
    },
    "foo": {
        "username": "foo",
        "password": pw_encryptor.hash_password("foo"),
        "permissions": {"can_manually_sync": False},
    },
}


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


@router.post(token_url)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login user and return access token (no refresh token for simplicity)."""
    user = users_db.get(form_data.username)  # User or None
    if not user or not pw_encryptor.verify_password(form_data.password, user.get("password")):
        # Do NOT treat separately a user not found or a bad password. Huackers! Huackers!!!!
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail="Invalid username or password"
        )

    access_token = _create_access_token(user)
    return {"access_token": access_token, "refresh_token": None, "token_type": "bearer"}


# Meh... typical usage having a /me endpoint. We will probably not use it but...
@router.get("/me")
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Decode token and return user info."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = users_db[payload["sub"]]
        user = copy.deepcopy(user)
        user.pop("password", None)
        return user
    except jwt.InvalidSignatureError:
        log.warning("Possible JWT tampering detected. Invalid signature.")
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except KeyError:
        # Don't use HTTP 404. That would give too much information to the huackers
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Nopes")
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unknown error. The team will look into it",
        )
