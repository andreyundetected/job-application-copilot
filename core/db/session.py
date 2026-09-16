from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db.models import Base
import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()