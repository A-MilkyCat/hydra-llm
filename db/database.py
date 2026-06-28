import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME", "hydradb")
DB_USER = os.getenv("DB_USER", "hydra_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()