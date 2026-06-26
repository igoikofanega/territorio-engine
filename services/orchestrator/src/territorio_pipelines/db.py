from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from .config import sync_database_url

engine = create_engine(sync_database_url(), future=True)
Base = declarative_base()
