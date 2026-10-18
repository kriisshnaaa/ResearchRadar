"""Exact and optional semantic deduplication.

Sentence-Transformers is used when available and a caller supplies/permits a model.
If it cannot load, exact URL/title deduplication remains available and callers
receive a warning rather than an unverified semantic result.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from hashlib import sha256
from typing import Any
from urllib.parse import urldefrag, urlsplit, urlunsplit

from ..models import Record

logger = logging.getLogger(__name__)


def deduplicate(records: list[Record], enabled: bool = True, threshold: float = 0.88,
                embedding_model: Any = None) -> tuple[list[Record], str | None]:
    exact: dict[str, Record] = {}
    for record in records:
        keys = [f"url:{canonical_url(record.url)}", f"title:{normalized_title(record.title)}"]
        existing = next((exact[key] for key in keys if key in exact), None)
        if existing is None:
            existing = record
        else:
            preferred = _preferred(existing, record)
            if preferred is not existing:
                _merge(preferred, existing)
                existing = preferred
            _merge(existing, record)
        for key in keys:
            exact[key] = existing
    unique: list[Record] = []
    seen_objects: set[int] = set()
    for record in exact.values():
        if id(record) not in seen_objects:
            seen_objects.add(id(record))
            unique.append(record)
    warning = None
    if enabled and len(unique) > 1:
        try:
            vectors = _embed(unique, embedding_model)
        except Exception as exc:
            warning = f"semantic dedup unavailable; exact deduplication used ({type(exc).__name__})"
            logger.warning(warning)
            vectors = None
        if vectors is not None:
            kept: list[Record] = []
            for index, item in enumerate(unique):
                match = next((j for j, prior in enumerate(kept)
                              if _cosine(vectors[index], vectors[unique.index(prior)]) >= threshold), None)
                if match is None:
                    kept.append(item)
                else:
                    _merge(kept[match], item)
            unique = kept
    for record in unique:
        record.duplicate_cluster_id = sha256(canonical_url(record.url).encode()).hexdigest()[:12]
    return unique, warning


def canonical_url(url: str) -> str:
    clean, _ = urldefrag(url.strip())
    parts = urlsplit(clean)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
                       parts.query, "")).lower()


def normalized_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def _merge(primary: Record, duplicate: Record) -> None:
    if duplicate.url not in primary.related_urls and duplicate.url != primary.url:
        primary.related_urls.append(duplicate.url)
    for url in duplicate.related_urls:
        if url not in primary.related_urls and url != primary.url:
            primary.related_urls.append(url)
    if len(duplicate.text) > len(primary.text):
        primary.text = duplicate.text
    if not primary.authors and duplicate.authors:
        primary.authors = duplicate.authors
    if not primary.published_at:
        primary.published_at = duplicate.published_at


def _embed(records: list[Record], model: Any = None) -> list[list[float]]:
    if model is None:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            logger.debug("Sentence-Transformers model unavailable: %s", exc)
            raise RuntimeError("Sentence-Transformers model unavailable") from exc
    encoded = model.encode([r.title + " " + r.text for r in records], normalize_embeddings=True)
    return [list(map(float, vector)) for vector in encoded]


def _preferred(left: Record, right: Record) -> Record:
    def score(record: Record) -> tuple[int, int, int, int, str]:
        return (
            len(record.text),
            1 if record.source_type == "arxiv" else 0,
            1 if record.published_at else 0,
            len(record.authors),
            record.url,
        )

    return left if score(left) >= score(right) else right


def _token_vector(text: str) -> list[float]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    vector = [0.0] * 256
    for token, count in Counter(tokens).items():
        # Fixed-width hashing keeps fallback vectors comparable without a model.
        index = int(sha256(token.encode("utf-8")).hexdigest()[:8], 16) % len(vector)
        vector[index] += float(count)
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
