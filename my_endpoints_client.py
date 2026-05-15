"""Minimal client for the my_endpoints contacts REST API."""
from __future__ import annotations

from typing import Any

import httpx


def _headers(bearer_token: str) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if bearer_token:
        h["Authorization"] = f"Bearer {bearer_token}"
    return h


async def check_health(base_url: str, timeout: float = 10.0) -> tuple[bool, str]:
    if not base_url:
        return False, "MY_ENDPOINTS_API_BASE_URL не задан"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/health")
        ok = 200 <= resp.status_code < 300
        return ok, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.HTTPError as e:
        return False, f"Ошибка: {e}"


async def create_contact(
    base_url: str,
    contact: dict[str, Any],
    bearer_token: str = "",
    timeout: float = 30.0,
) -> tuple[bool, str, dict[str, Any] | None]:
    if not base_url:
        return False, "MY_ENDPOINTS_API_BASE_URL не задан", None
    url = f"{base_url.rstrip('/')}/api/v1/contacts"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(bearer_token), json={"data": contact})
    except httpx.HTTPError as e:
        return False, f"Сетевая ошибка: {e}", None

    body: dict[str, Any] | None = None
    try:
        body = resp.json() if resp.content else None
    except ValueError:
        body = None

    if 200 <= resp.status_code < 300:
        return True, f"HTTP {resp.status_code}", body
    return False, f"HTTP {resp.status_code}: {resp.text[:300]}", body
