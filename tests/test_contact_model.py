"""Tests for canonical contact mapping."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contact_model import build_canonical_contact, short_preview  # noqa: E402


def test_full_mapping():
    extracted = {
        "full_name": "Иван Иванович Петров",
        "company": "ООО Ромашка",
        "position": "Директор",
        "phone_mobile": ["+7 999 123-45-67"],
        "phone_work": ["+7 495 111-22-33"],
        "email": "ivan@example.com",
        "telegram": "@ivanp",
        "whatsapp": "+79991234567",
        "city": "Москва",
        "country": "Россия",
        "address": "ул. Тверская, 1",
        "website": "https://example.com",
    }
    c = build_canonical_contact(extracted)
    assert c["doc-type"] == "person"
    assert c["deleted"] is False
    assert c["known"] is True

    person = c["person"]
    assert person["origin"] == "telegram-image-ingest"
    assert person["name"]["full_name"] == "Иван Иванович Петров"
    assert person["name"]["first_name"] == "Иван"
    assert person["name"]["middle_name"] == "Иванович"
    assert person["name"]["last_name"] == "Петров"

    phone = person["contact-details"]["phone"]
    assert phone["mobile"] == ["+7 999 123-45-67"]
    assert phone["work"] == ["+7 495 111-22-33"]
    assert phone["prefered"] == "+7 999 123-45-67"

    msg = person["contact-details"]["messengers"]
    assert msg["telegram"]["login"] == "ivanp"  # @ stripped
    assert msg["whatsapp"]["phone"] == "+79991234567"

    raw = person["contact-details"]["raw"]
    assert "email: ivan@example.com" in raw
    assert "website: https://example.com" in raw

    assert person["jobs"][0]["company"]["organization-name"] == "ООО Ромашка"
    assert person["jobs"][0]["position"] == "Директор"

    occ = person["occupation"][0]
    assert occ["city"] == "Москва"
    assert occ["country"] == "Россия"
    assert occ["address"] == "ул. Тверская, 1"

    assert person["quick-notes"][0]["note"]
    assert person["quick-notes"][0]["date"]


def test_empty_extraction_safe():
    c = build_canonical_contact({})
    p = c["person"]
    assert p["name"]["full_name"] == ""
    assert p["contact-details"]["phone"]["mobile"] == []
    assert p["jobs"][0]["company"]["organization-name"] == ""
    assert p["contact-details"]["messengers"]["telegram"]["login"] == ""


def test_phones_generic_merged_into_mobile():
    c = build_canonical_contact({"phones": ["+1 111", "+2 222"]})
    assert c["person"]["contact-details"]["phone"]["mobile"] == ["+1 111", "+2 222"]


def test_first_last_assembled_into_full_name():
    c = build_canonical_contact({"first_name": "Анна", "last_name": "Смирнова"})
    assert c["person"]["name"]["full_name"] == "Анна Смирнова"


def test_preview_has_key_fields():
    c = build_canonical_contact(
        {"full_name": "Test User", "email": "t@u.com", "company": "Acme", "position": "CTO"}
    )
    out = short_preview(c)
    assert "Test User" in out
    assert "Acme" in out
    assert "t@u.com" in out


def test_hyphenated_keys_preserved():
    c = build_canonical_contact({"full_name": "X"})
    assert "doc-type" in c
    assert "created-date" in c
    assert "modified-date" in c
    p = c["person"]
    assert "quick-notes" in p
    assert "contact-details" in p
    assert "first-met" in p
    assert "important-dates" in p
    assert "realated-persons" in p  # preserved as in spec (typo intentional)
