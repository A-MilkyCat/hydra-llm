from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, nullable=False, index=True)
    password   = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    keys = relationship("ApiKey", back_populates="user", uselist=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), unique=True)
    keys_blob    = Column(Text, nullable=False)  # JSON 陣列，加密後存
    hydra_token  = Column(String, unique=True, nullable=False, index=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="keys")