"""Official google-genai SDK adapter with bounded retry and output validation."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from ..models import Digest, Record
from .prompts import build_prompt

logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    pass


class GeminiSummarizer:
    def __init__(self, api_key: str | None, model: str, max_input_chars: int = 30000,
                 retries: int = 2, client: Any = None):
        self.api_key, self.model, self.max_input_chars, self.retries = api_key, model, max_input_chars, retries
        self.client = client

    def summarize(self, topic: str, records: list[Record]) -> Digest:
        if not records:
            raise GeminiError("cannot summarize an empty item list")
        if not self.api_key and self.client is None:
            raise GeminiError("GEMINI_API_KEY is not configured")
        if self.client is None:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                raise GeminiError("could not initialize google-genai client") from exc
        prompts = [build_prompt(topic, records, self.max_input_chars), build_prompt(
            topic, records, self.max_input_chars, simple=True)]
        last_error: Exception | None = None
        for index, prompt in enumerate(prompts):
            try:
                response = self.client.models.generate_content(model=self.model, contents=prompt)
                text = _response_text(response)
                _validate_output(text, records)
                return Digest(text=text)
            except Exception as exc:
                last_error = exc
                if index == 0:
                    time.sleep(0.5)
                    continue
        raise GeminiError(f"Gemini returned no valid digest: {type(last_error).__name__}") from last_error


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    if isinstance(response, dict):
        return str(response.get("text") or response.get("output_text") or "").strip()
    return ""


def _validate_output(text: str, records: list[Record]) -> None:
    if not text or len(text) < 20:
        raise ValueError("empty or malformed Gemini output")
    allowed = {record.url for record in records} | {url for record in records for url in record.related_urls}
    urls = set(re.findall(r"https?://[^\s)\]>]+", text))
    if any(url.rstrip(".,") not in allowed for url in urls):
        raise ValueError("Gemini output contains an URL not present in evidence")
