import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> frozenset[int]:
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    return frozenset(out)


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
    my_endpoints_base_url: str
    my_endpoints_bearer_token: str
    http_timeout: float


def load_config() -> Config:
    return Config(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        allowed_user_ids=_parse_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "").strip(),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip(),
        my_endpoints_base_url=os.getenv("MY_ENDPOINTS_API_BASE_URL", "").strip().rstrip("/"),
        my_endpoints_bearer_token=os.getenv("MY_ENDPOINTS_BEARER_TOKEN", "").strip(),
        http_timeout=float(os.getenv("HTTP_TIMEOUT", "60")),
    )
