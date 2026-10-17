"""Environment-backed configuration with safe validation."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return parsed


def _float(name: str, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


@dataclass(frozen=True)
class Settings:
    gemini_api_key: Optional[str]
    gemini_model: str
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    news_api_provider: str
    gnews_api_key: Optional[str]
    rss_feeds: tuple[str, ...]
    arxiv_max_results: int
    news_max_results: int
    rss_max_results_per_feed: int
    max_total_items: int
    min_text_length: int
    semantic_dedup_enabled: bool
    semantic_dedup_threshold: float
    only_new_items: bool
    sqlite_path: str
    request_timeout_seconds: float
    max_retries: int
    gemini_max_input_chars: int
    telegram_max_message_chars: int
    log_level: str

    @classmethod
    def from_env(cls, env_file: Optional[str] = None, require_delivery: bool = True) -> "Settings":
        load_dotenv(env_file)
        provider = os.getenv("NEWS_API_PROVIDER", "disabled").strip().lower()
        if provider not in {"disabled", "gnews"}:
            raise ValueError("NEWS_API_PROVIDER must be 'disabled' or 'gnews'")
        settings = cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            news_api_provider=provider,
            gnews_api_key=os.getenv("GNEWS_API_KEY") or None,
            rss_feeds=tuple(x.strip() for x in os.getenv("RSS_FEEDS", "").split(",") if x.strip()),
            arxiv_max_results=_int("ARXIV_MAX_RESULTS", 10, 1),
            news_max_results=_int("NEWS_MAX_RESULTS", 10, 1),
            rss_max_results_per_feed=_int("RSS_MAX_RESULTS_PER_FEED", 10, 1),
            max_total_items=_int("MAX_TOTAL_ITEMS", 30, 1),
            min_text_length=_int("MIN_TEXT_LENGTH", 40, 0),
            semantic_dedup_enabled=_bool("SEMANTIC_DEDUP_ENABLED", True),
            semantic_dedup_threshold=_float("SEMANTIC_DEDUP_THRESHOLD", 0.88),
            only_new_items=_bool("ONLY_NEW_ITEMS", False),
            sqlite_path=os.getenv("SQLITE_PATH", "data/researchradar.db"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
            max_retries=_int("MAX_RETRIES", 3, 0),
            gemini_max_input_chars=_int("GEMINI_MAX_INPUT_CHARS", 30000, 1000),
            telegram_max_message_chars=_int("TELEGRAM_MAX_MESSAGE_CHARS", 3500, 100),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
        missing = settings.missing_required(require_delivery=require_delivery)
        if missing:
            raise ValueError("Missing configuration variables: " + ", ".join(missing))
        return settings

    def missing_required(self, require_delivery: bool = True) -> list[str]:
        missing: list[str] = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if require_delivery and not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if require_delivery and not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if self.news_api_provider == "gnews" and not self.gnews_api_key:
            missing.append("GNEWS_API_KEY")
        return missing

    @property
    def database_path(self) -> Path:
        return Path(self.sqlite_path)
