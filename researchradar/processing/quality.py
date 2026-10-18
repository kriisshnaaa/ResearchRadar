"""Transparent quality and topic-relevance checks."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models import Record


def filter_quality(records: list[Record], min_text_length: int = 40, require_relevance: bool = True) -> list[Record]:
    output: list[Record] = []
    for record in records:
        if not record.title or not record.url or not record.valid_url():
            continue
        if not record.text or len(record.text.strip()) < min_text_length:
            # arXiv abstracts are structured evidence; don't discard short,
            # valid abstracts solely because a news/RSS threshold is configured.
            if record.source_type != "arxiv" or not record.text.strip():
                continue
        if _looks_like_error(record.text):
            continue
        if require_relevance and not is_relevant(record):
            continue
        output.append(record)
    return output


def is_relevant(record: Record) -> bool:
    terms = _tokens(record.topic)
    if not terms:
        return True
    title_tokens = set(_tokens(record.title))
    body_tokens = _tokens(record.text)
    title_matches = sum(term in title_tokens for term in terms)
    body_matches = sum(term in body_tokens for term in terms)
    if title_matches == len(terms):
        return True
    if len(terms) == 1:
        return body_tokens.count(terms[0]) >= 2
    required_matches = max(2, (len(terms) + 1) // 2)
    return title_matches >= 1 and title_matches + body_matches >= required_matches


def _tokens(text: str) -> list[str]:
    stopwords = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "using", "with"}
    return [
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in stopwords
    ]


def _looks_like_error(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"error", "access denied", "not found", "forbidden"} or "captcha" in lowered
