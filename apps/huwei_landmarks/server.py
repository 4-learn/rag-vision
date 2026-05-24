"""LINE BOT webhook server for 虎尾地標辨識

FastAPI app that receives LINE webhook events, verifies the signature,
downloads image messages, runs the RAG pipeline, and replies to the user.

跑法：
    uvicorn apps.huwei_landmarks.server:app --host 0.0.0.0 --port 8000

或透過 docker compose：
    docker compose up

環境變數：
    LINE_CHANNEL_ACCESS_TOKEN  (必要)
    LINE_CHANNEL_SECRET        (必要)
    GEMINI_API_KEY 或 GOOGLE_API_KEY (必要，傳給 pipeline)
    LANDMARKS_SHEET_CSV_URL    (可選，覆寫預設 Sheet URL)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import ImageMessageContent, MessageEvent, TextMessageContent

from . import line_bot
from . import session_manager
from .db import init_db
from .system_prompt import (
    GOODBYE_TIMEOUT,
    GOODBYE_USER_INITIATED,
    is_end_keyword,
)

load_dotenv()
init_db()

logger = logging.getLogger("huwei_landmarks.server")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# ---------- 設定讀取 ----------

def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"缺少必要環境變數：{name}")
    return val


def _gemini_key() -> str:
    """Pipeline 用的金鑰，GEMINI_API_KEY 優先、退而求其次 GOOGLE_API_KEY。"""
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    )


UNSUPPORTED_MESSAGE = "我看不懂這種訊息耶 🤔 你可以傳文字跟我聊、或傳一張地標照片給我認"


# ---------- FastAPI App ----------

app = FastAPI(title="Huwei Landmarks LINE BOT")


def _get_parser() -> WebhookParser:
    """Lazy-build parser；延後讀環境變數方便測試覆寫。"""
    return WebhookParser(_require_env("LINE_CHANNEL_SECRET"))


def _get_messaging_config() -> Configuration:
    return Configuration(access_token=_require_env("LINE_CHANNEL_ACCESS_TOKEN"))


def _extract_signature(headers) -> str:
    """LINE header 是 `X-Line-Signature`，但 HTTP header 大小寫不敏感。

    Starlette 的 Headers 介面本身已 case-insensitive，這裡再做一次
    fallback，以防中間經過 reverse proxy 把 header 名稱改成全小寫。
    """
    return (
        headers.get("x-line-signature")
        or headers.get("X-Line-Signature")
        or ""
    )


@app.get("/")
async def root() -> dict:
    return {"service": "huwei-landmarks-line-bot", "status": "ok"}


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.post("/tasks/scan-timeouts")
async def scan_timeouts() -> dict:
    """Ch5：掃所有 idle 超過 SESSION_TIMEOUT_MINUTES 的 active session，
    標記結束 + push「告別訊息」給 user。

    部署方式：用 docker-compose 內的 cron container 每分鐘 POST 一次此端點。
    （不放 internal scheduler、避免跟 uvicorn worker count 互動）
    """
    timed_out = session_manager.find_timed_out_sessions()
    if not timed_out:
        return {"ended": 0, "users": []}

    pushed_users: list[str] = []
    config = _get_messaging_config()
    with ApiClient(config) as api_client:
        messaging_api = MessagingApi(api_client)
        for sess in timed_out:
            session_manager.end_session(sess.id, "timeout")
            try:
                messaging_api.push_message(
                    PushMessageRequest(to=sess.user_id, messages=[TextMessage(text=GOODBYE_TIMEOUT)])
                )
                pushed_users.append(sess.user_id)
            except Exception:  # noqa: BLE001
                # push 失敗（user block / LINE API 503） — log 後繼續
                logger.exception("push goodbye to %s failed", sess.user_id)

    return {"ended": len(timed_out), "users": pushed_users}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """LINE Platform 的 webhook 進入點。

    LINE 要求 webhook 回應 < 10 秒；Gemini 兩階段通常 15-25 秒，因此
    這裡 verify + parse 後立刻 return 200，實際處理丟到 BackgroundTasks
    非同步跑，reply_token 在 60 秒內仍可用。
    """
    signature = _extract_signature(request.headers)
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8")

    parser = _get_parser()
    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature on /webhook; rejecting request")
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        background_tasks.add_task(_process_event_background, event)

    return {"status": "ok", "events": len(events)}


def _process_event_background(event) -> None:
    """在 background thread 跑的事件處理。每次開新 ApiClient（thread-safe）。"""
    try:
        config = _get_messaging_config()
        with ApiClient(config) as api_client:
            messaging_api = MessagingApi(api_client)
            blob_api = MessagingApiBlob(api_client)
            _handle_event(event, messaging_api, blob_api)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to handle event in background: %r", event)


# ---------- Event routing ----------

def _handle_event(
    event,
    messaging_api: MessagingApi,
    blob_api: MessagingApiBlob,
) -> None:
    """Dispatch single webhook event."""
    if not isinstance(event, MessageEvent):
        logger.debug("Ignoring non-message event: %s", type(event).__name__)
        return

    message = event.message
    reply_token = event.reply_token

    user_id = getattr(event.source, "user_id", None) or "unknown"

    if isinstance(message, ImageMessageContent):
        _handle_image_event(user_id, message.id, reply_token, blob_api, messaging_api)
        return

    if isinstance(message, TextMessageContent):
        _handle_text_event(user_id, message.text, reply_token, messaging_api)
        return

    # 其他類型（sticker / location / audio…） — 禮貌回一句
    logger.info("Received unsupported message type: %s", type(message).__name__)
    _reply_text(messaging_api, reply_token, UNSUPPORTED_MESSAGE)


def _handle_text_event(
    user_id: str,
    text: str,
    reply_token: Optional[str],
    messaging_api: MessagingApi,
) -> None:
    """Ch5：文字訊息 → session 管理 + LLM 對話。

    流程：
    1. 結束關鍵字 → end_session + 告別訊息（reply）
    2. 否則 → session_manager.chat() → 回覆
    """
    if is_end_keyword(text):
        sess = session_manager.get_active_session(user_id)
        if sess is not None:
            session_manager.end_session(sess.id, "user")
        _reply_text(messaging_api, reply_token, GOODBYE_USER_INITIATED)
        return

    reply_text = session_manager.chat(user_id, text)
    _reply_text(messaging_api, reply_token, reply_text)


def _handle_image_event(
    user_id: str,
    message_id: str,
    reply_token: str,
    blob_api: MessagingApiBlob,
    messaging_api: MessagingApi,
) -> None:
    image_bytes = _download_image(blob_api, message_id)
    reply_text = line_bot.handle_image_message(image_bytes)
    _reply_text(messaging_api, reply_token, reply_text)

    # Ch5：圖片辨識結果也寫進 session、讓後續文字對話能 reference 到。
    # 例：使用者傳圖認出虎尾驛 → 接著問「它附近有什麼？」 bot 能接住「它」=虎尾驛。
    try:
        sess = session_manager.get_active_session(user_id) or session_manager.start_session(user_id)
        # 用人話描述「使用者傳了圖」，讓 LLM 後續能看懂上下文
        session_manager.write_image_turn(sess.id, reply_text)
    except Exception:  # noqa: BLE001
        # session 寫失敗不應影響圖片辨識回覆（已經 reply 給使用者了）
        logger.exception("write image turn into session failed for user %s", user_id)


def _download_image(blob_api: MessagingApiBlob, message_id: str) -> bytes:
    """透過 LINE SDK 下載 image message 內容。

    SDK 回傳 bytearray / bytes，這裡統一成 bytes 方便下游使用。
    """
    content = blob_api.get_message_content(message_id=message_id)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    # SDK 不同版本可能回傳 file-like；做個保底
    read = getattr(content, "read", None)
    if callable(read):
        return read()
    raise TypeError(f"Unexpected content type from LINE blob API: {type(content)!r}")


def _reply_text(messaging_api: MessagingApi, reply_token: Optional[str], text: str) -> None:
    if not reply_token:
        return
    messaging_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=text)],
        )
    )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "apps.huwei_landmarks.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("RELOAD")),
    )
