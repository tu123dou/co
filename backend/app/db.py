from sqlalchemy import create_engine
from .config import settings

engine = create_engine(
    settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5
)
query_engine = create_engine(
    settings().query_database_url, pool_pre_ping=True, pool_size=3, max_overflow=3
)
