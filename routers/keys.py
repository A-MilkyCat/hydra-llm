from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import json
import secrets

from db.database import get_db
from db.models import User, ApiKey

router = APIRouter(prefix="/keys", tags=["Keys"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

class KeysRequest(BaseModel):
    keys: list[str]

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def generate_hydra_token() -> str:
    return f"hydra-sk-{secrets.token_urlsafe(32)}"

@router.post("")
def submit_keys(
    request: KeysRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.keys:
        raise HTTPException(status_code=400, detail="Keys already exist, use PUT to update")

    hydra_token = generate_hydra_token()
    api_key = ApiKey(
        user_id=user.id,
        keys_blob=json.dumps(request.keys),
        hydra_token=hydra_token
    )
    db.add(api_key)
    db.commit()
    return {"hydra_token": hydra_token}

@router.get("")
def get_keys(
    user: User = Depends(get_current_user),
):
    if not user.keys:
        raise HTTPException(status_code=404, detail="No keys found")
    return {"keys": json.loads(user.keys.keys_blob)}

@router.put("")
def update_keys(
    request: KeysRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user.keys:
        raise HTTPException(status_code=404, detail="No keys found, use POST to create")

    user.keys.keys_blob = json.dumps(request.keys)
    user.keys.updated_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"message": "keys updated"}

@router.delete("")
def delete_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user.keys:
        raise HTTPException(status_code=404, detail="No keys found")

    db.delete(user.keys)
    db.commit()
    return {"message": "keys deleted"}

@router.post("/rotate")
def rotate_token(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user.keys:
        raise HTTPException(status_code=404, detail="No keys found")

    user.keys.hydra_token = generate_hydra_token()
    db.commit()
    return {"hydra_token": user.keys.hydra_token}