"""Typed models shared by sources, processing, persistence, and delivery."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
from urllib.parse import urlparse


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SourceStatus:
    source_type: str
    source_name: str
    attempted: bool = True
    success: bool = False
    item_count: int = 0
    error: Optional[str] = None


@dataclass
class Record:
    id: str
    title: str
    source_type: str
    source_name: str
    url: str
    published_at: Optional[str]
    authors: list[str]
    text: str
    topic: str
    retrieved_at: str
    content_hash: str
    related_urls: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    duplicate_cluster_id: Optional[str] = None

    @classmethod
    def create(
        cls, title: str, source_type: str, source_name: str, url: str,
        text: str, topic: str, published_at: Optional[str] = None,
        authors: Optional[list[str]] = None, retrieved_at: Optional[str] = None,
    ) -> "Record":
        normalized = " ".join((title or "").lower().split()) + "|" + url.strip().lower()
        content_hash = sha256(normalized.encode("utf-8")).hexdigest()
        return cls(
            id=content_hash[:24], title=title.strip(), source_type=source_type,
            source_name=source_name.strip(), url=url.strip(), published_at=published_at,
            authors=authors or [], text=text.strip(), topic=topic.strip(),
            retrieved_at=retrieved_at or utc_now(), content_hash=content_hash,
        )

    def valid_url(self) -> bool:
        parsed = urlparse(self.url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def evidence_text(self, limit: int = 4000) -> str:
        return self.text[:limit]


@dataclass
class Digest:
    text: str
    item_summaries: dict[str, str] = field(default_factory=dict)


@dataclass
class CollectionResult:
    items: list[Record]
    status: SourceStatus
