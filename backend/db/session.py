from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.db.models import Base


class OrchestratorDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path.as_posix()}",
            future=True,
            poolclass=NullPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)
