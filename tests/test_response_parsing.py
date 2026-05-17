"""Tests for HTTP response parsing in openrouter and my_endpoints clients."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from my_endpoints_client import parse_create_contact_response  # noqa: E402
from openrouter_client import parse_openrouter_response  # noqa: E402


def _resp(status: int, body: object, *, as_json: bool = True) -> httpx.Response:
    if as_json:
        content = json.dumps(body).encode("utf-8")
        return httpx.Response(status, content=content, headers={"content-type": "application/json"})
    return httpx.Response(status, content=str(body).encode("utf-8"))


def test_openrouter_returns_parsed_content_dict():
    extracted = {"full_name": "Иван Петров", "email": "i@p.com"}
    payload = {
        "choices": [
            {"message": {"content": json.dumps(extracted, ensure_ascii=False)}}
        ]
    }
    resp = _resp(200, payload)
    assert parse_openrouter_response(resp) == extracted


def test_openrouter_handles_list_content_with_text_parts():
    extracted = {"full_name": "X"}
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": json.dumps(extracted)},
                    ]
                }
            }
        ]
    }
    assert parse_openrouter_response(_resp(200, payload)) == extracted


def test_openrouter_strips_markdown_fences():
    extracted = {"full_name": "Y"}
    fenced = "```json\n" + json.dumps(extracted) + "\n```"
    payload = {"choices": [{"message": {"content": fenced}}]}
    assert parse_openrouter_response(_resp(200, payload)) == extracted


def test_openrouter_http_error_includes_status_and_body():
    resp = _resp(429, "rate limited", as_json=False)
    with pytest.raises(RuntimeError) as ei:
        parse_openrouter_response(resp)
    msg = str(ei.value)
    assert "429" in msg
    assert "rate limited" in msg
    assert "Response" not in msg  # never expose the raw Response object


def test_openrouter_non_json_body_raises_with_status():
    resp = _resp(200, "response 200 ok", as_json=False)
    with pytest.raises(ValueError) as ei:
        parse_openrouter_response(resp)
    msg = str(ei.value)
    assert "200" in msg
    assert "response 200 ok" in msg


def test_openrouter_missing_choices_includes_payload_excerpt():
    resp = _resp(200, {"error": {"message": "bad model"}})
    with pytest.raises(ValueError) as ei:
        parse_openrouter_response(resp)
    msg = str(ei.value)
    assert "bad model" in msg
    assert "Response" not in msg


def test_openrouter_non_json_model_content_includes_raw():
    payload = {"choices": [{"message": {"content": "response 200 — not json"}}]}
    with pytest.raises(ValueError) as ei:
        parse_openrouter_response(_resp(200, payload))
    assert "response 200" in str(ei.value)


def test_my_endpoints_parses_json_body_on_success():
    resp = _resp(201, {"uuid": "abc-123", "ok": True})
    ok, msg, body = parse_create_contact_response(resp)
    assert ok is True
    assert "201" in msg
    assert body == {"uuid": "abc-123", "ok": True}


def test_my_endpoints_handles_non_json_success_body():
    resp = _resp(200, "saved", as_json=False)
    ok, msg, body = parse_create_contact_response(resp)
    assert ok is True
    assert "200" in msg
    assert body is None


def test_my_endpoints_failure_includes_status_and_body():
    resp = _resp(500, "internal explode", as_json=False)
    ok, msg, body = parse_create_contact_response(resp)
    assert ok is False
    assert "500" in msg
    assert "internal explode" in msg
    assert body is None


def test_my_endpoints_failure_with_json_body_keeps_dict():
    resp = _resp(422, {"error": "validation", "fields": ["email"]})
    ok, msg, body = parse_create_contact_response(resp)
    assert ok is False
    assert "422" in msg
    assert "validation" in msg
    assert body == {"error": "validation", "fields": ["email"]}


def test_my_endpoints_returns_none_body_for_empty_response():
    resp = httpx.Response(204, content=b"")
    ok, msg, body = parse_create_contact_response(resp)
    assert ok is True
    assert body is None
