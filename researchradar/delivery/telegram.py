"""Telegram Bot API delivery using HTTPS POST and conservative message chunks."""
from __future__ import annotations

import time
from typing import Any

import requests


class TelegramDeliveryError(RuntimeError):
    pass


def split_message(text: str, max_chars: int = 3500) -> list[str]:
    if not text:
        return []
    if max_chars < 100:
        raise ValueError("max_chars is too small")
    parts: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        cut = _safe_cut(remaining, max_chars)
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


def _safe_cut(text: str, limit: int) -> int:
    candidates = [text.rfind("\n\n", 0, limit), text.rfind("\n", 0, limit), text.rfind(" ", 0, limit)]
    cut = max(candidates)
    if cut <= 0:
        cut = limit
    # Never split inside a URL where a paragraph has no convenient boundary.
    last_open = text.rfind("http", 0, cut)
    last_close = max(text.rfind(" ", 0, cut), text.rfind("\n", 0, cut))
    if last_open > last_close:
        # Leave the complete URL for the next part rather than cutting it or
        # exceeding Telegram's configured bound.
        if last_close > 0:
            cut = last_close
    return cut


class TelegramDelivery:
    def __init__(self, token: str | None, chat_id: str | None, timeout: float = 20,
                 max_chars: int = 3500, retries: int = 2, post: Any = None):
        self.token, self.chat_id, self.timeout = token, chat_id, timeout
        self.max_chars, self.retries, self.post = max_chars, retries, post or requests.post
        self.sent_parts = 0

    def send(self, text: str) -> int:
        if not self.token or not self.chat_id:
            raise TelegramDeliveryError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        parts = split_message(text, self.max_chars)
        if not parts:
            raise TelegramDeliveryError("cannot send an empty digest")
        for part in parts:
            self._send_part(part)
            self.sent_parts += 1
        return self.sent_parts

    def _send_part(self, part: str) -> None:
        endpoint = f"https://api.telegram.org/bot{self.token}/sendMessage"
        for attempt in range(self.retries + 1):
            try:
                response = self.post(endpoint, json={"chat_id": self.chat_id, "text": part},
                                     timeout=self.timeout)
                payload = response.json()
                if response.status_code == 429 and attempt < self.retries:
                    time.sleep(_retry_after(payload))
                    continue
                if response.status_code >= 500 and attempt < self.retries:
                    time.sleep(min(2 ** attempt, 4))
                    continue
                if response.status_code >= 400 or not isinstance(payload, dict) or payload.get("ok") is not True:
                    description = payload.get("description", "Telegram API error") if isinstance(payload, dict) else "invalid response"
                    raise TelegramDeliveryError(f"Telegram delivery failed (status {response.status_code}): {description}")
                return
            except requests.Timeout as exc:
                if attempt >= self.retries:
                    raise TelegramDeliveryError("Telegram request timed out") from exc
                time.sleep(min(2 ** attempt, 4))
            except ValueError as exc:
                raise TelegramDeliveryError("Telegram returned invalid JSON") from exc


def _retry_after(payload: Any) -> float:
    try:
        return min(float(payload["parameters"]["retry_after"]), 10)
    except (KeyError, TypeError, ValueError):
        return 1.0
