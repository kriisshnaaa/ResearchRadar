"""HTTP helpers shared by connectors; secrets are never included in errors."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

import requests


RETRYABLE = {429, 500, 502, 503, 504}


def request_with_retry(
    method: str,
    url: str,
    *,
    timeout: float,
    retries: int,
    params: Optional[dict[str, Any]] = None,
    json: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    request: Callable[..., Any] = requests.request,
) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = request(method, url, params=params, json=json, headers=headers, timeout=timeout)
            if response.status_code in RETRYABLE and attempt < retries:
                time.sleep(min(2 ** attempt, 4))
                continue
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 4))
                continue
            raise RuntimeError("request timed out or could not connect") from exc
        except requests.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in RETRYABLE and attempt < retries:
                time.sleep(min(2 ** attempt, 4))
                continue
            raise RuntimeError(f"HTTP request failed (status {status or 'unknown'})") from exc
    raise RuntimeError("request failed") from last_error
