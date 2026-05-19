"""Minimal OpenRouter vision client for contact extraction."""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

EXTRACTION_PROMPT = (
    "Extract contact details from the image (business card, email signature, contact photo) "
    "and return STRICTLY JSON without explanations and without markdown wrappers. "
    "Use only these keys (omit missing ones): "
    "full_name, first_name, middle_name, last_name, gender, "
    "company, position, address, city, country, "
    "phone_mobile (list of strings), phone_work (list), phone_home (list), phones (list), "
    "email, emails (list), telegram, whatsapp, website, websites (list), "
    "notes, raw_text (list of strings with any other text from the image). "
    "Phone numbers — in international format if possible. Telegram — without @. "
    "If a field is not found — do NOT include the key. Return only the JSON object."
)


def _shorten(text: str, limit: int = 500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[: -3]
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        return json.loads(match.group(0))
    raise ValueError(
        f"Failed to parse JSON from model response. Content: {_shorten(text)!r}"
    )


def parse_openrouter_response(resp: httpx.Response) -> dict[str, Any]:
    """Parse an OpenRouter chat-completions Response into the extracted contact dict.

    Raises with status code and a short raw body on any failure, so the caller
    never has to stringify the Response object itself (which would render as
    `<Response [200 OK]>` and hide the actual payload).
    """
    status = resp.status_code
    raw_text = resp.text or ""

    if not (200 <= status < 300):
        raise RuntimeError(
            f"OpenRouter HTTP {status}: {_shorten(raw_text)}"
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise ValueError(
            f"OpenRouter HTTP {status}: response is not valid JSON. Body: {_shorten(raw_text)!r}"
        ) from e

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(
            f"Unexpected OpenRouter response format (HTTP {status}): "
            f"{_shorten(json.dumps(payload, ensure_ascii=False))}"
        ) from e

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = "\n".join(text_parts)

    if not isinstance(content, str):
        raise ValueError(
            f"OpenRouter returned content that is not a string: {type(content).__name__}"
        )

    return _extract_json(content)


async def extract_contact_from_image(
    image_bytes: bytes,
    mime_type: str,
    api_key: str,
    model: str,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: float = 60.0,
) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    if not model:
        raise RuntimeError("OPENROUTER_MODEL is not set")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DmitryBashkov/my_endpoints-telegram-ingest-bot",
        "X-Title": "my_endpoints-telegram-ingest-bot",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )

    return parse_openrouter_response(resp)
