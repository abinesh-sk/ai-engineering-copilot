import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # test each connection with a lightweight ping before use; transparently reconnects if dead
    pool_recycle=300,     # proactively recycle connections older than 5 min, before Neon can close them first
)
def check_connection():
    with engine.connect() as conn:
        result=conn.execute(text("SELECT version();"))
        return result.fetchone()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()