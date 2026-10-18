"""Official arXiv Atom API connector."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Optional

from ..models import CollectionResult, Record, SourceStatus
from .http import request_with_retry


ATOM = "http://www.w3.org/2005/Atom"


class ArxivSource:
    name = "arXiv"
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: float = 20, retries: int = 3, max_results: int = 10, request: Any = None):
        self.timeout, self.retries, self.max_results = timeout, retries, max_results
        self.request = request

    def fetch(self, topic: str) -> CollectionResult:
        status = SourceStatus("arxiv", self.name)
        try:
            response = request_with_retry(
                "GET", self.endpoint, timeout=self.timeout, retries=self.retries,
                params={"search_query": f"all:{topic}", "start": 0, "max_results": self.max_results,
                        "sortBy": "submittedDate", "sortOrder": "descending"},
                request=self.request or __import__("requests").request,
            )
            root = ET.fromstring(response.text)
            items: list[Record] = []
            for entry in root.findall(f"{{{ATOM}}}entry"):
                title = _text(entry, "title")
                abstract = _text(entry, "summary")
                url = _text(entry, "id")
                if not title or not abstract or not url:
                    continue
                authors = [_text(author, "name") for author in entry.findall(f"{{{ATOM}}}author")]
                published = _text(entry, "published") or _text(entry, "updated")
                items.append(Record.create(title, "arxiv", self.name, url, abstract, topic, published, authors))
            status.success, status.item_count = True, len(items)
            return CollectionResult(items, status)
        except (ET.ParseError, RuntimeError, ValueError) as exc:
            status.error = f"invalid arXiv response: {exc}" if isinstance(exc, ET.ParseError) else str(exc)
            return CollectionResult([], status)


def _text(element: Optional[ET.Element], tag: str) -> str:
    if element is None:
        return ""
    child = element.find(f"{{{ATOM}}}{tag}")
    return " ".join((child.text or "").split()) if child is not None else " ".join((element.text or "").split())
