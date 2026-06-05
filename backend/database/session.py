from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.config import load_database_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = load_database_settings()
    connect_args = {"check_same_thread": False} if settings.url.startswith("sqlite") else {}
    return create_engine(settings.url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session
