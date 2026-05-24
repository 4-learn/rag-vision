"""DB connection + session helpers.

啟動時自動 create_all（無 alembic、避免教學情境多裝套件）。
SQLite 預設用 /app/data/sessions.db；docker-compose 會 mount host ./data。

⚠️ ai-eva：把 DATABASE_URL 換成 postgresql+psycopg2://... 即可、其他不用動。
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from .models import Base


def _default_db_url() -> str:
    """Default to SQLite in /app/data/sessions.db (mounted volume in docker)."""
    data_dir = Path(os.environ.get("RAG_KIT_DATA_DIR", "/app/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir}/sessions.db"


DATABASE_URL = os.environ.get("DATABASE_URL") or _default_db_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    # SQLite 在多 thread 共用同一個 connection 時需要這個 flag
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if not exist. 啟動時呼叫一次即可。"""
    Base.metadata.create_all(engine)


@contextmanager
def db_session():
    """`with db_session() as s:` — auto commit / rollback / close."""
    s: OrmSession = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
