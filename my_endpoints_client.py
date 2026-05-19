"""Minimal client for the my_endpoints contacts REST API."""
from __future__ import annotations

from typing import Any

import httpx


def _headers(bearer_token: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if bearer_token:
        h["Authorization"] = f"Bearer {bearer_token}"
    return h


def _shorten(text: str, limit: int = 300) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def parse_create_contact_response(resp: httpx.Response) -> tuple[bool, str, dict[str, Any] | None]:
    """Inspect a my_endpoints POST response and return (ok, message, body).

    Never returns the raw Response object — callers get a small dict (parsed
    JSON) or None, plus a human-readable status string with HTTP code and a
    short body excerpt on failure.
    """
    status = resp.status_code
    raw_text = resp.text or ""

    body: dict[str, Any] | None = None
    if resp.content:
        try:
            parsed = resp.json()
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            body = parsed

    if 200 <= status < 300:
        return True, f"HTTP {status}", body
    return False, f"HTTP {status}: {_shorten(raw_text)}", body


async def check_health(base_url: str, timeout: float = 10.0) -> tuple[bool, str]:
    if not base_url:
        return False, "MY_ENDPOINTS_API_BASE_URL is not set"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/health")
        ok = 200 <= resp.status_code < 300
        return ok, f"HTTP {resp.status_code}: {_shorten(resp.text, 200)}"
    except httpx.HTTPError as e:
        return False, f"Error: {e}"


async def create_contact(
    base_url: str,
    contact: dict[str, Any],
    bearer_token: str = "",
    timeout: float = 30.0,
) -> tuple[bool, str, dict[str, Any] | None]:
    if not base_url:
        return False, "MY_ENDPOINTS_API_BASE_URL is not set", None
    url = f"{base_url.rstrip('/')}/api/v1/contacts"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(bearer_token), json={"data": contact})
    except httpx.HTTPError as e:
        return False, f"Network error: {e}", None

    return parse_create_contact_response(resp)
