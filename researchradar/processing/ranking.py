"""Deterministic heuristic ranking, not a scientific relevance score."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import Record


SOURCE_WEIGHT = {"arxiv": 1.0, "news": 0.9, "blog": 0.8}


def rank_items(records: list[Record], topic: str, max_total: int = 30,
               per_source: int | None = None) -> list[Record]:
    topic_terms = set(re.findall(r"[a-z0-9]+", topic.lower()))
    for record in records:
        tokens = set(re.findall(r"[a-z0-9]+", (record.title + " " + record.text).lower()))
        overlap = len(topic_terms & tokens) / max(1, len(topic_terms))
        completeness = (0.1 if record.authors else 0) + (0.1 if record.published_at else 0)
        record.relevance_score = round(overlap + SOURCE_WEIGHT.get(record.source_type, 0.5) * 0.1 + completeness, 6)
    ordered = sorted(records, key=lambda r: (-r.relevance_score, -_timestamp(r), r.source_type, r.title.lower(), r.url))
    if per_source is None:
        return ordered[:max_total]
    counts: dict[str, int] = {}
    bounded: list[Record] = []
    for record in ordered:
        if counts.get(record.source_type, 0) >= per_source:
            continue
        counts[record.source_type] = counts.get(record.source_type, 0) + 1
        bounded.append(record)
        if len(bounded) >= max_total:
            break
    return bounded


def _timestamp(record: Record) -> float:
    if not record.published_at:
        return 0.0
    try:
        return datetime.fromisoformat(record.published_at.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0
