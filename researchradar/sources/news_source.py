"""News provider interface and GNews implementation.

GNews uses the documented GET https://gnews.io/api/v4/search endpoint.
The free plan currently advertises 100 requests/day, up to 10 articles/request,
30-day history, 12-hour freshness delay, and truncated content; plans can change.
"""
from __future__ import annotations

from typing import Any, Protocol

import requests

from ..models import CollectionResult, Record, SourceStatus
from .http import request_with_retry


class NewsProvider(Protocol):
    def fetch(self, topic: str) -> CollectionResult: ...


class GNewsSource:
    name = "GNews"
    endpoint = "https://gnews.io/api/v4/search"

    def __init__(self, api_key: str | None, timeout: float = 20, retries: int = 3,
                 max_results: int = 10, request: Any = None):
        self.api_key, self.timeout, self.retries, self.max_results = api_key, timeout, retries, max_results
        self.request = request

    def fetch(self, topic: str) -> CollectionResult:
        status = SourceStatus("news", self.name)
        if not self.api_key:
            status.error = "GNews disabled: GNEWS_API_KEY is not configured"
            return CollectionResult([], status)
        try:
            response = request_with_retry(
                "GET", self.endpoint, timeout=self.timeout, retries=self.retries,
                params={"q": topic, "lang": "en", "max": min(self.max_results, 100), "apikey": self.api_key},
                request=self.request or requests.request,
            )
            payload = response.json()
            articles = payload.get("articles") if isinstance(payload, dict) else None
            if not isinstance(articles, list):
                raise ValueError("response does not contain an articles list")
            items: list[Record] = []
            for article in articles[: self.max_results]:
                if not isinstance(article, dict):
                    continue
                title, url = str(article.get("title") or "").strip(), str(article.get("url") or "").strip()
                description = str(article.get("description") or article.get("content") or "").strip()
                source = article.get("source") if isinstance(article.get("source"), dict) else {}
                source_name = str(source.get("name") or "GNews")
                if title and url and description:
                    items.append(Record.create(title, "news", source_name, url, description, topic,
                                               article.get("publishedAt"), []))
            status.success, status.item_count = True, len(items)
            return CollectionResult(items, status)
        except (ValueError, RuntimeError, requests.RequestException) as exc:
            status.error = f"invalid GNews response: {exc}" if isinstance(exc, ValueError) else str(exc)
            return CollectionResult([], status)


def make_news_source(provider: str, api_key: str | None, **kwargs: Any) -> NewsProvider:
    if provider == "gnews":
        return GNewsSource(api_key, **kwargs)
    return DisabledNewsSource()


class DisabledNewsSource:
    def fetch(self, topic: str) -> CollectionResult:
        return CollectionResult([], SourceStatus("news", "News (disabled)", success=False,
                                                 error="news provider is disabled"))
