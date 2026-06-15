import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url  # <-- Add this to parse the URL safely
from sqlalchemy.orm import declarative_base, sessionmaker
from urllib.parse import quote_plus     # <-- Add this to escape the password

raw_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agroai")

# 1. Safely break down the URL components even if it has special characters
parsed_url = make_url(raw_url)

# 2. Extract and URL-encode the password if it exists
if parsed_url.password:
    encoded_password = quote_plus(parsed_url.password)
    # Reassemble the URL with the safe, escaped password
    DATABASE_URL = parsed_url.set(password=encoded_password).render_as_string(hide_password=False)
else:
    DATABASE_URL = raw_url

# SQLite needs connect_args={"check_same_thread": False}
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency generator for SQLAlchemy database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()