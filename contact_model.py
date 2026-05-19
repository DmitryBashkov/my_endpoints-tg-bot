"""Build the canonical my_endpoints person contact JSON from extracted fields."""
from __future__ import annotations

from datetime import date
from typing import Any


def _s(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            s = _s(item)
            if s:
                out.append(s)
        return out
    return [_s(value)] if _s(value) else []


def _split_name(full_name: str) -> tuple[str, str, str]:
    parts = full_name.split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def build_canonical_contact(extracted: dict[str, Any]) -> dict[str, Any]:
    """Map an LLM-extracted flat dict to canonical my_endpoints person JSON.

    Expected (loose) keys: full_name, first_name, middle_name, last_name,
    gender, company, position, address, city, country,
    phone_mobile, phone_work, phone_home, phones (list),
    email, emails (list), telegram, whatsapp, website, websites (list),
    notes, raw_text.
    """
    today = date.today().isoformat()

    full_name = _s(extracted.get("full_name"))
    first_name = _s(extracted.get("first_name"))
    middle_name = _s(extracted.get("middle_name"))
    last_name = _s(extracted.get("last_name"))
    if not full_name and (first_name or last_name):
        full_name = " ".join(p for p in [first_name, middle_name, last_name] if p)
    if full_name and not (first_name or last_name):
        first_name, middle_name, last_name = _split_name(full_name)

    name_raw = _list_of_str(extracted.get("name_raw")) or ([full_name] if full_name else [])

    mobile = _list_of_str(extracted.get("phone_mobile"))
    work = _list_of_str(extracted.get("phone_work"))
    home = _list_of_str(extracted.get("phone_home"))
    generic_phones = _list_of_str(extracted.get("phones"))
    for ph in generic_phones:
        if ph not in mobile and ph not in work and ph not in home:
            mobile.append(ph)

    emails = _list_of_str(extracted.get("emails"))
    single_email = _s(extracted.get("email"))
    if single_email and single_email not in emails:
        emails.insert(0, single_email)

    websites = _list_of_str(extracted.get("websites"))
    single_site = _s(extracted.get("website"))
    if single_site and single_site not in websites:
        websites.insert(0, single_site)

    telegram_login = _s(extracted.get("telegram"))
    if telegram_login.startswith("@"):
        telegram_login = telegram_login[1:]
    whatsapp_phone = _s(extracted.get("whatsapp"))

    raw_lines: list[str] = []
    for e in emails:
        raw_lines.append(f"email: {e}")
    for w in websites:
        raw_lines.append(f"website: {w}")
    raw_extra = _list_of_str(extracted.get("raw_text"))
    raw_lines.extend(raw_extra)

    company = _s(extracted.get("company"))
    position = _s(extracted.get("position"))
    jobs: list[dict[str, Any]] = []
    if company or position:
        jobs.append(
            {
                "last-date": "",
                "company": {"organization-uuid": "", "organization-name": company},
                "position": position,
                "comments": "",
            }
        )
    else:
        jobs.append(
            {
                "last-date": "",
                "company": {"organization-uuid": "", "organization-name": ""},
                "position": "",
                "comments": "",
            }
        )

    address = _s(extracted.get("address"))
    city = _s(extracted.get("city"))
    country = _s(extracted.get("country"))
    occupation = [
        {
            "last-date": "",
            "city": city,
            "country": country,
            "address": address,
        }
    ]

    note = _s(extracted.get("notes")) or "Imported from image via Telegram bot"
    quick_notes = [{"date": today, "note": note}]

    prefered = ""
    if mobile:
        prefered = mobile[0]
    elif work:
        prefered = work[0]
    elif home:
        prefered = home[0]

    return {
        "doc-type": "person",
        "created-date": today,
        "modified-date": today,
        "deleted": False,
        "known": True,
        "person": {
            "uuid": "",
            "origin": "telegram-image-ingest",
            "quick-notes": quick_notes,
            "name": {
                "raw": name_raw,
                "full_name": full_name,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
            },
            "gender": _s(extracted.get("gender")),
            "contact-details": {
                "raw": raw_lines,
                "phone": {
                    "home": home,
                    "mobile": mobile,
                    "work": work,
                    "emergency": [],
                    "prefered": prefered,
                },
                "messengers": {
                    "telegram": {"login": telegram_login, "phone": ""},
                    "whatsapp": {"phone": whatsapp_phone},
                },
            },
            "occupation": occupation,
            "first-met": {
                "date": "",
                "who": {"person-uuid": "", "full-name": ""},
                "where": "",
                "context": "",
            },
            "jobs": jobs,
            "important-dates": [],
            "interests": [],
            "capabilities": [],
            "realated-persons": [],
        },
    }


def short_preview(canonical: dict[str, Any]) -> str:
    person = canonical.get("person", {})
    name = person.get("name", {}).get("full_name", "") or "(no name)"
    cd = person.get("contact-details", {})
    phones = cd.get("phone", {})
    mobile = ", ".join(phones.get("mobile", []))
    work = ", ".join(phones.get("work", []))
    tg = cd.get("messengers", {}).get("telegram", {}).get("login", "")
    wa = cd.get("messengers", {}).get("whatsapp", {}).get("phone", "")
    raw = cd.get("raw", [])
    email = next((line[len("email: "):] for line in raw if line.startswith("email: ")), "")
    jobs = person.get("jobs", [])
    company = jobs[0]["company"]["organization-name"] if jobs else ""
    position = jobs[0]["position"] if jobs else ""
    note = ""
    qn = person.get("quick-notes", [])
    if qn:
        note = qn[0].get("note", "")

    lines = [f"<b>Name:</b> {name}"]
    if company or position:
        lines.append(f"<b>Company/position:</b> {company} — {position}".rstrip(" —"))
    if mobile:
        lines.append(f"<b>Mobile:</b> {mobile}")
    if work:
        lines.append(f"<b>Work:</b> {work}")
    if email:
        lines.append(f"<b>Email:</b> {email}")
    if tg:
        lines.append(f"<b>Telegram:</b> @{tg}")
    if wa:
        lines.append(f"<b>WhatsApp:</b> {wa}")
    if note:
        lines.append(f"<b>Note:</b> {note}")
    return "\n".join(lines)
