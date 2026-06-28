from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os

from db.database import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

class AuthRequest(BaseModel):
    email: EmailStr
    password: str

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

def create_jwt(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )

@router.post("/register")
def register(request: AuthRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=request.email,
        password=hash_password(request.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "registered successfully"}

@router.post("/login")
def login(request: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(user.id)
    return {"access_token": token, "token_type": "bearer"}