"""Canonical record cleanup and stable identifiers."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from ..models import Record


def normalize_record(record: Record) -> Record:
    record.title = re.sub(r"\s+", " ", record.title or "").strip()
    record.text = re.sub(r"\s+", " ", record.text or "").strip()
    record.url = record.url.strip()
    record.authors = [re.sub(r"\s+", " ", a).strip() for a in record.authors if a and a.strip()]
    if record.published_at:
        record.published_at = _normalize_date(record.published_at)
    return record


def normalize_records(records: Iterable[Record]) -> list[Record]:
    return [normalize_record(record) for record in records]


def _normalize_date(value: str) -> str:
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return text
