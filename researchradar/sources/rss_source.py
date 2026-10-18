"""RSS/Atom connector. It consumes feed metadata, never scrapes article pages."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

from ..models import CollectionResult, Record, SourceStatus
from .http import request_with_retry


class RSSSource:
    def __init__(self, feeds: tuple[str, ...] | list[str], timeout: float = 20,
                 max_results_per_feed: int = 10, parser: Any = None):
        self.feeds = tuple(feeds)
        self.timeout = timeout
        self.max_results_per_feed = max_results_per_feed
        self.parser = parser

    def fetch(self, topic: str) -> CollectionResult:
        if not self.feeds:
            return CollectionResult([], SourceStatus("blog", "RSS", success=False,
                                                     error="RSS_FEEDS is not configured"))
        items: list[Record] = []
        errors: list[str] = []
        for feed_url in self.feeds:
            try:
                if self.parser is not None:
                    parsed = self.parser(feed_url, request_headers={"User-Agent": "ResearchRadar/1.0"})
                else:
                    response = request_with_retry(
                        "GET", feed_url, headers={"User-Agent": "ResearchRadar/1.0"},
                        timeout=self.timeout, retries=2, request=requests.request,
                    )
                    parsed = feedparser.parse(response.content)
                if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
                    raise ValueError("malformed feed")
                feed_name = str(getattr(parsed, "feed", {}).get("title") or feed_url)
                entries = getattr(parsed, "entries", [])[: self.max_results_per_feed]
                for entry in entries:
                    title = str(entry.get("title") or "").strip()
                    url = str(entry.get("link") or "").strip()
                    text = str(entry.get("summary") or entry.get("description") or "").strip()
                    if title and url and text:
                        items.append(Record.create(title, "blog", feed_name, url, text, topic,
                                                   _entry_date(entry)))
            except Exception as exc:
                errors.append(f"{feed_url}: {type(exc).__name__}")
        status = SourceStatus("blog", "RSS", success=not errors or bool(items), item_count=len(items))
        if errors:
            status.error = "; ".join(errors)
        return CollectionResult(items, status)


def _entry_date(entry: Any) -> str | None:
    value = entry.get("published") or entry.get("updated")
    if value:
        return str(value)
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        return datetime(*struct[:6], tzinfo=timezone.utc).isoformat()
    return None
