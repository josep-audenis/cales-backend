from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Import models so SQLModel.metadata knows about all tables before create_all().
import app.db.models  # noqa: F401

engine = create_engine(settings.database_url, echo=False, connect_args={"check_same_thread": False})


def create_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
