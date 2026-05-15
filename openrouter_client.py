"""Minimal OpenRouter vision client for contact extraction."""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

EXTRACTION_PROMPT = (
    "Извлеки контактные данные с изображения (визитка, подпись email, фото контакта) "
    "и верни СТРОГО JSON без пояснений и без markdown-обёрток. "
    "Используй только эти ключи (опускай отсутствующие): "
    "full_name, first_name, middle_name, last_name, gender, "
    "company, position, address, city, country, "
    "phone_mobile (list of strings), phone_work (list), phone_home (list), phones (list), "
    "email, emails (list), telegram, whatsapp, website, websites (list), "
    "notes, raw_text (list of строк с любым другим текстом с изображения). "
    "Телефоны — в международном формате если возможно. Telegram — без @. "
    "Если поле не найдено — НЕ включай ключ. Верни только JSON-объект."
)


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
    raise ValueError("Не удалось распарсить JSON из ответа модели")


async def extract_contact_from_image(
    image_bytes: bytes,
    mime_type: str,
    api_key: str,
    model: str,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: float = 60.0,
) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан")
    if not model:
        raise RuntimeError("OPENROUTER_MODEL не задан")

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
        resp.raise_for_status()
        data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Неожиданный формат ответа OpenRouter: {data}") from e

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        content = "\n".join(text_parts)

    return _extract_json(content)
