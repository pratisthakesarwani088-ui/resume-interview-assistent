"""
Thin HTTP client for the FastAPI AI service (Module 8). This is the ONLY
place in Django that knows the AI service's URL/auth scheme — analysis,
assistant, and rag's services.py files call `post()` here instead of each
constructing their own HTTP request, so there's one spot to change if the
AI service's transport details ever change.

This module intentionally has no knowledge of Gemini, prompts, or any
business logic — it just moves a JSON payload to a path on the AI service
and hands back the JSON response, or raises AIServiceHTTPError.
"""

import httpx
from django.conf import settings


class AIServiceHTTPError(Exception):
    """Raised for any failure talking to the AI service: not configured,
    unreachable, timed out, or it returned a non-2xx response."""


def _base_url() -> str:
    if not settings.AI_SERVICE_URL:
        raise AIServiceHTTPError("AI_SERVICE_URL is not configured on the server.")
    return settings.AI_SERVICE_URL.rstrip("/")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.AI_SERVICE_INTERNAL_KEY:
        headers["X-Internal-Api-Key"] = settings.AI_SERVICE_INTERNAL_KEY
    return headers


def post(path: str, payload: dict, timeout: float = 60.0) -> dict:
    """POSTs `payload` as JSON to `{AI_SERVICE_URL}{path}` and returns the
    parsed JSON response. `path` should start with '/', e.g. '/chat'."""
    url = f"{_base_url()}{path}"
    try:
        response = httpx.post(url, json=payload, headers=_headers(), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AIServiceHTTPError(
            f"AI service returned {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    except httpx.RequestError as exc:
        raise AIServiceHTTPError(f"Could not reach the AI service: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceHTTPError("AI service returned a non-JSON response.") from exc
