# It’s the file that connects your Python code to the database. 
# Anything that wants to read or save data uses this file.
# Without it, every file would set up its own connection with its own password handling and configuration.
# With it, the connection is set up once in one place, and closing is automatic.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()