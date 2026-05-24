"""SQLAlchemy ORM models for LINE Bot session memory.

Ch5「對話記憶」核心 schema。設計概念：

- 一個 LINE user 同時最多 1 個 active session（ended_at IS NULL）。
- 結束後的 session **不刪**，保留供分析或寫總結。
- `last_message_at` 用來判 timeout（30 min idle）。
- end_reason 區分「user 自己結束 (bye/再見/end)」vs「timeout 自動結束」。

⚠️ ai-eva Claude Code 抄這份時：
- user_id 概念跟你那邊一樣是 LINE userId（U 開頭 32 hex）
- DB 連線只要在 db.py 換 PostgreSQL URI 即可（無 schema 差異）
- 不需要 import 我們的 rag-kit pipeline，純粹 session 管理
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    """一次 LINE 對話的容器。

    生命週期：start_session 建一筆 → 收訊息累積 last_message_at →
    user 喊結束 / 30min idle → end_session 寫 ended_at + end_reason。
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    end_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (
        # 同一 user 應該最多 1 筆 ended_at IS NULL；用 partial index 跨方言不通用，這裡只做 index 加速查詢。
        Index("ix_sessions_user_active", "user_id", "ended_at"),
    )


class Message(Base):
    """Session 內的單則訊息。

    role 只用 "user" / "assistant"，方便直接組成 OpenAI / Gemini messages 格式。
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    session: Mapped[Session] = relationship(back_populates="messages")
