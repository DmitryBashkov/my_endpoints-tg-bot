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


def _opt_str(name: str) -> str:
    return os.getenv(name, "").strip()


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
    telegram_connect_timeout: float
    telegram_read_timeout: float
    telegram_write_timeout: float
    telegram_pool_timeout: float
    telegram_proxy_url: str
    telegram_get_updates_proxy_url: str
    telegram_startup_retry_delay: float


def load_config() -> Config:
    proxy_url = _opt_str("TELEGRAM_PROXY_URL")
    get_updates_proxy_url = _opt_str("TELEGRAM_GET_UPDATES_PROXY_URL") or proxy_url
    return Config(
        telegram_bot_token=_opt_str("TELEGRAM_BOT_TOKEN"),
        allowed_user_ids=_parse_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")),
        openrouter_api_key=_opt_str("OPENROUTER_API_KEY"),
        openrouter_model=_opt_str("OPENROUTER_MODEL"),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip(),
        my_endpoints_base_url=os.getenv("MY_ENDPOINTS_API_BASE_URL", "").strip().rstrip("/"),
        my_endpoints_bearer_token=_opt_str("MY_ENDPOINTS_BEARER_TOKEN"),
        http_timeout=float(os.getenv("HTTP_TIMEOUT", "60")),
        telegram_connect_timeout=float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "30")),
        telegram_read_timeout=float(os.getenv("TELEGRAM_READ_TIMEOUT", "30")),
        telegram_write_timeout=float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "30")),
        telegram_pool_timeout=float(os.getenv("TELEGRAM_POOL_TIMEOUT", "30")),
        telegram_proxy_url=proxy_url,
        telegram_get_updates_proxy_url=get_updates_proxy_url,
        telegram_startup_retry_delay=float(os.getenv("TELEGRAM_STARTUP_RETRY_DELAY", "15")),
    )
