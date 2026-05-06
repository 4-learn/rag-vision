"""Gemini Generator

呼叫 Google Gemini API 生成回答。支援 multimodal (text + image)。

從原本的 detect.detect_landmark() 拆出來，讓 Generator 不再綁死地標領域：
- prompt template 由 app 層（huwei_landmarks）提供
- 欄位組裝也由 app 層決定

進階功能（v2）：條件性多模態
- 若 payload 的 row 帶 reference photo URL/path,自動 download + 塞進 prompt
- 沒帶的 row 走純文字快路徑(向後相容)
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, Callable

import requests


class GeminiGenerator:
    """用 Gemini API 做生成。

    Args:
        api_key: Google API Key
        model:   Gemini 模型名稱（預設 gemini-2.5-flash）
        prompt_builder: callable(payload, query) -> str，組出 prompt 文字
        response_mime_type: 預設 "application/json"
        reference_photo_column: 選填,row dict 中存 reference photo URL/path 的 key
        key_column: 選填,row dict 中存地標名的 key(用來標 reference 是哪個地標)
        reference_timeout_sec: download reference photo 的 timeout
    """

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        prompt_builder: Callable[[dict, Any], str],
        model: str = "gemini-2.5-flash",
        response_mime_type: str = "application/json",
        reference_photo_column: str | None = None,
        key_column: str | None = None,
        reference_timeout_sec: float = 10.0,
    ):
        self.api_key = api_key
        self.model = model
        self.prompt_builder = prompt_builder
        self.response_mime_type = response_mime_type
        self.reference_photo_column = reference_photo_column
        self.key_column = key_column
        self.reference_timeout_sec = reference_timeout_sec
        # In-memory cache: ref source(URL/path) → (bytes, mime)
        self._ref_cache: dict[str, tuple[bytes, str]] = {}

    def _fetch_reference(self, source: str) -> tuple[bytes, str] | None:
        """下載/讀取 reference photo,回 (bytes, mime_type)。失敗回 None。"""
        if source in self._ref_cache:
            return self._ref_cache[source]

        try:
            if source.startswith(("http://", "https://")):
                resp = requests.get(source, timeout=self.reference_timeout_sec)
                resp.raise_for_status()
                content = resp.content
                mime = resp.headers.get("Content-Type", "image/jpeg")
                # 有時 Content-Type 帶 ; charset=...,只取前段
                mime = mime.split(";", 1)[0].strip()
            else:
                # 視為 local path
                p = Path(source)
                if not p.exists():
                    return None
                content = p.read_bytes()
                ext = p.suffix.lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
        except Exception:
            return None

        self._ref_cache[source] = (content, mime)
        return content, mime

    def _build_reference_parts(self, rows: list[dict]) -> list[dict]:
        """掃 rows,有 reference 就加進 parts。沒設 reference_photo_column 時直接回 []。"""
        if not self.reference_photo_column:
            return []
        parts: list[dict] = []
        for row in rows:
            ref = (row.get(self.reference_photo_column) or "").strip()
            if not ref:
                continue
            fetched = self._fetch_reference(ref)
            if not fetched:
                continue
            content, mime = fetched
            name = (
                (row.get(self.key_column) or "").strip()
                if self.key_column
                else "(unknown)"
            )
            parts.append({"text": f"\n[reference photo of 「{name}」]"})
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": base64.b64encode(content).decode(),
                }
            })
        return parts

    def generate(self, payload: dict, query: Any) -> str:
        prompt_text = self.prompt_builder(payload, query)

        parts: list[dict] = [{"text": prompt_text}]

        # 條件性多模態:有 reference photo 的 row 加進 prompt
        ref_parts = self._build_reference_parts(payload.get("rows", []))
        parts.extend(ref_parts)

        # query 支援 {"image_bytes": bytes, "mime_type": "image/png"} 或 str
        if isinstance(query, dict) and "image_bytes" in query:
            img_b64 = base64.b64encode(query["image_bytes"]).decode()
            parts.append({"text": "\n[使用者照片]"})
            parts.append({
                "inline_data": {
                    "mime_type": query.get("mime_type", "image/png"),
                    "data": img_b64,
                }
            })

        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"
        resp = requests.post(url, json={
            "contents": [{"parts": parts}],
            "generationConfig": {
                "response_mime_type": self.response_mime_type,
            },
        })

        data = resp.json()
        if "error" in data:
            return json.dumps({"error": data["error"]["message"]}, ensure_ascii=False)

        return data["candidates"][0]["content"]["parts"][0]["text"]
