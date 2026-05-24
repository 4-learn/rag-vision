"""Session 生命週期 + LLM 對話的核心邏輯。

對外提供 5 個 function：
- start_session(user_id)
- end_session(session, reason)
- get_active_session(user_id)
- find_timed_out_sessions(idle_minutes=30)
- chat(user_id, user_text)  ← 包整個 user-input → LLM reply 的 happy path

⚠️ ai-eva 抄這份時：
- 我們用 Gemini REST（rag-kit 既有 stack），你那邊改成 LiteLLM call
  → 整個 _call_llm() 內換掉就行
- 其他 (lifecycle / context 組裝 / timeout scan) 完全照抄
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests
from sqlalchemy import select

from .db import db_session
from .models import Message, Session
from .system_prompt import CHAT_SYSTEM_PROMPT


logger = logging.getLogger("huwei_landmarks.session_manager")


# 最多保留多少則歷史塞給 LLM（避免 prompt 過長）
DEFAULT_CONTEXT_TURNS = 12

# Timeout 預設 30 min（讓 .env 可調，課堂 demo 會調短）
DEFAULT_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "30"))


# ────────────────────────────────────────────────────────────
# Lifecycle
# ────────────────────────────────────────────────────────────

def start_session(user_id: str) -> Session:
    """為 user 開一個新 session、回傳。

    若 user 已經有 active session（程式 bug 或 race），先把它 end 掉。
    """
    with db_session() as s:
        existing = s.execute(
            select(Session).where(Session.user_id == user_id, Session.ended_at.is_(None))
        ).scalar_one_or_none()
        if existing:
            logger.warning("user %s already has active session %d; ending it first", user_id, existing.id)
            existing.ended_at = datetime.utcnow()
            existing.end_reason = "replaced"

        new_session = Session(user_id=user_id)
        s.add(new_session)
        s.flush()  # 拿到 id
        sid = new_session.id
    # 重新查一次（detached → fresh）
    return _refetch_session(sid)


def end_session(session_id: int, reason: str) -> Optional[Session]:
    """標記 session 結束。reason: 'user' / 'timeout' / 'replaced' / 其他。"""
    with db_session() as s:
        sess = s.get(Session, session_id)
        if sess is None or sess.ended_at is not None:
            return sess
        sess.ended_at = datetime.utcnow()
        sess.end_reason = reason
    return _refetch_session(session_id)


def get_active_session(user_id: str) -> Optional[Session]:
    """拿 user 目前進行中的 session（沒有就回 None）。"""
    with db_session() as s:
        return s.execute(
            select(Session).where(Session.user_id == user_id, Session.ended_at.is_(None))
        ).scalar_one_or_none()


def find_timed_out_sessions(idle_minutes: int = None) -> list[Session]:
    """掃所有 active session、回傳 idle 超過 N 分鐘的。

    給 scheduler / cron / /tasks/scan-timeouts 端點呼叫。
    """
    threshold_min = idle_minutes if idle_minutes is not None else DEFAULT_TIMEOUT_MINUTES
    threshold = datetime.utcnow() - timedelta(minutes=threshold_min)
    with db_session() as s:
        rows = s.execute(
            select(Session)
            .where(Session.ended_at.is_(None))
            .where(Session.last_message_at < threshold)
        ).scalars().all()
        # detach 避免外部用到 closed session
        return [_clone(r) for r in rows]


# ────────────────────────────────────────────────────────────
# Chat
# ────────────────────────────────────────────────────────────

def chat(user_id: str, user_text: str) -> str:
    """收使用者一則文字 → 拿 active session（沒有就建）→ append message →
    組 context → call LLM → append assistant message → 回 reply 文字。

    結束關鍵字的判斷不在這層；由 server.py 在進來之前處理掉。
    """
    sess = get_active_session(user_id)
    if sess is None:
        sess = start_session(user_id)

    # append user message + 更新 last_message_at
    _add_message(sess.id, "user", user_text)
    _touch_session(sess.id)

    # 撈最近 N 則歷史（含剛剛這則 user message）
    history = _get_recent_messages(sess.id, limit=DEFAULT_CONTEXT_TURNS)

    # 組 LLM messages（系統 prompt + 歷史）
    llm_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in history
    ]

    try:
        reply = _call_llm(llm_messages)
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM call failed for user %s: %s", user_id, e)
        reply = "我這邊暫時遇到問題，請等等再傳一次給我 🙏"

    # append assistant message
    _add_message(sess.id, "assistant", reply)
    _touch_session(sess.id)

    return reply


def write_image_turn(session_id: int, identification_reply: str) -> None:
    """把「使用者剛剛傳了張圖、bot 認出 / 回覆內容」這對話寫進 session。

    用途：圖片流程跟文字流程共用 session，後續文字對話 (chat()) 才能看到
    使用者剛剛傳了什麼圖、bot 認出來什麼地標。

    寫兩筆 message：
    - role=user, content="[使用者傳了一張地標照片給你看]"
    - role=assistant, content=圖片辨識的回覆（line_bot.handle_image_message 的 return）

    這樣下一輪 chat() 拿 history 時，LLM 看得到「我剛剛認過某地標」的上下文。
    """
    _add_message(session_id, "user", "[使用者傳了一張地標照片給你看]")
    _add_message(session_id, "assistant", identification_reply)
    _touch_session(session_id)


# ────────────────────────────────────────────────────────────
# Internals
# ────────────────────────────────────────────────────────────

def _add_message(session_id: int, role: str, content: str) -> None:
    with db_session() as s:
        s.add(Message(session_id=session_id, role=role, content=content))


def _touch_session(session_id: int) -> None:
    with db_session() as s:
        sess = s.get(Session, session_id)
        if sess is not None:
            sess.last_message_at = datetime.utcnow()


def _get_recent_messages(session_id: int, limit: int) -> list[Message]:
    with db_session() as s:
        rows = s.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        ).scalars().all()
        # 取出後 reverse 成由舊到新
        return list(reversed([_clone_msg(r) for r in rows]))


def _refetch_session(session_id: int) -> Session:
    with db_session() as s:
        sess = s.get(Session, session_id)
        if sess is None:
            raise RuntimeError(f"Session {session_id} disappeared")
        return _clone(sess)


def _clone(sess: Session) -> Session:
    """淺複製成獨立 instance（避免 caller 用到 detached / closed session）。"""
    c = Session()
    c.id = sess.id
    c.user_id = sess.user_id
    c.started_at = sess.started_at
    c.last_message_at = sess.last_message_at
    c.ended_at = sess.ended_at
    c.end_reason = sess.end_reason
    c.summary = sess.summary
    return c


def _clone_msg(m: Message) -> Message:
    c = Message()
    c.id = m.id
    c.session_id = m.session_id
    c.role = m.role
    c.content = m.content
    c.created_at = m.created_at
    return c


# ────────────────────────────────────────────────────────────
# LLM call (Gemini REST — rag-kit 既有 stack)
#
# ai-eva 抄這份時，把這個 function 換掉就好；其他不動。
# ────────────────────────────────────────────────────────────

_GEMINI_MODEL = os.environ.get("CHAT_GEMINI_MODEL", "gemini-2.5-flash")


def _call_llm(messages: list[dict]) -> str:
    """把 OpenAI 格式的 messages 轉成 Gemini REST request、call、parse 回 string."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY 或 GOOGLE_API_KEY")

    # Gemini systemInstruction 跟 contents 分開傳
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    history = [m for m in messages if m["role"] != "system"]

    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in history
    ]

    body = {
        "systemInstruction": {"parts": [{"text": system_msg}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1500,
            # Gemini 2.5 預設會花 token 在 thinking、output 被擠壓。對話場景不需要、關掉。
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent?key={api_key}"
    )
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        logger.warning("Unexpected Gemini response shape: %s", data)
        return "（這次沒拿到回應，再試一次）"
