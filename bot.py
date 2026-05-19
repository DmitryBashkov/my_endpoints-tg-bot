"""Telegram bot: import contacts from images into my_endpoints."""
from __future__ import annotations

import io
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, load_config
from contact_model import build_canonical_contact, short_preview
from my_endpoints_client import check_health, create_contact
from openrouter_client import extract_contact_from_image

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("ingest-bot")

DRAFT_TTL_SECONDS = 30 * 60
DRAFTS: dict[int, dict[str, Any]] = {}


def _is_allowed(cfg: Config, user_id: int) -> bool:
    if not cfg.allowed_user_ids:
        return False
    return user_id in cfg.allowed_user_ids


def _prune_drafts() -> None:
    now = time.time()
    stale = [uid for uid, d in DRAFTS.items() if now - d.get("ts", 0) > DRAFT_TTL_SECONDS]
    for uid in stale:
        DRAFTS.pop(uid, None)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Save", callback_data="save"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ],
            [InlineKeyboardButton("📄 JSON", callback_data="json")],
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    if not user or not _is_allowed(cfg, user.id):
        await update.message.reply_text("Access denied.")
        log.warning("Denied /start from user_id=%s", user.id if user else "?")
        return
    await update.message.reply_text(
        "Hello! Send a photo of a business card or email signature — I'll extract the contact and "
        "show you a preview for confirmation before saving.\n\n"
        "Commands: /health — check services."
    )


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    if not user or not _is_allowed(cfg, user.id):
        await update.message.reply_text("Access denied.")
        return

    ok, msg = await check_health(cfg.my_endpoints_base_url, timeout=cfg.http_timeout)
    or_ok = bool(cfg.openrouter_api_key and cfg.openrouter_model)
    lines = [
        f"my_endpoints: {'✅' if ok else '❌'} {msg}",
        f"OpenRouter env: {'✅' if or_ok else '❌'} "
        f"(key {'set' if cfg.openrouter_api_key else 'missing'}, "
        f"model {'set' if cfg.openrouter_model else 'missing'})",
    ]
    await update.message.reply_text("\n".join(lines))


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    if not user or not _is_allowed(cfg, user.id):
        if update.message:
            await update.message.reply_text("Access denied.")
        log.warning("Denied image from user_id=%s", user.id if user else "?")
        return

    _prune_drafts()
    msg = update.message
    if not msg:
        return

    file_id: str | None = None
    mime_type = "image/jpeg"
    if msg.photo:
        file_id = msg.photo[-1].file_id
        mime_type = "image/jpeg"
    elif msg.document and (msg.document.mime_type or "").startswith("image/"):
        file_id = msg.document.file_id
        mime_type = msg.document.mime_type or "image/jpeg"

    if not file_id:
        await msg.reply_text("Please send an image (photo or image file).")
        return

    status = await msg.reply_text("⏳ Extracting contact…")
    try:
        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        image_bytes = buf.getvalue()
    except Exception as e:
        log.exception("Failed to download image")
        await status.edit_text(f"Failed to download image: {e}")
        return

    try:
        extracted = await extract_contact_from_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            api_key=cfg.openrouter_api_key,
            model=cfg.openrouter_model,
            base_url=cfg.openrouter_base_url,
            timeout=cfg.http_timeout,
        )
    except Exception as e:
        log.exception("OpenRouter extraction failed")
        await status.edit_text(f"Extraction error: {e}")
        return

    canonical = build_canonical_contact(extracted)
    DRAFTS[user.id] = {"ts": time.time(), "contact": canonical}

    preview = short_preview(canonical)
    await status.edit_text(
        f"Contact found:\n\n{preview}\n\nSave to database?",
        parse_mode=ParseMode.HTML,
        reply_markup=_confirm_keyboard(),
    )


async def _send_json_chunks(update: Update, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    chunk_size = 3500
    for i in range(0, len(text), chunk_size):
        await update.callback_query.message.reply_text(
            f"<pre>{text[i : i + chunk_size]}</pre>", parse_mode=ParseMode.HTML
        )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    query = update.callback_query
    if not query or not query.from_user:
        return
    user_id = query.from_user.id
    if not _is_allowed(cfg, user_id):
        await query.answer("Access denied.", show_alert=True)
        return

    await query.answer()
    action = query.data
    draft = DRAFTS.get(user_id)

    if action == "cancel":
        DRAFTS.pop(user_id, None)
        await query.edit_message_text("Cancelled. Draft deleted.")
        return

    if not draft:
        await query.edit_message_text("Draft not found or expired. Please send an image again.")
        return

    contact = draft["contact"]

    if action == "json":
        await _send_json_chunks(update, contact)
        return

    if action == "save":
        ok, msg, body = await create_contact(
            base_url=cfg.my_endpoints_base_url,
            contact=contact,
            bearer_token=cfg.my_endpoints_bearer_token,
            timeout=cfg.http_timeout,
        )
        if ok:
            uid = ""
            if isinstance(body, dict):
                uid = (
                    body.get("uuid")
                    or body.get("uid")
                    or (body.get("data") or {}).get("uuid")
                    or ""
                )
            suffix = f"\nuuid: {uid}" if uid else ""
            DRAFTS.pop(user_id, None)
            await query.edit_message_text(f"✅ Saved. {msg}{suffix}")
        else:
            await query.edit_message_text(f"❌ Failed to save.\n{msg}")
        return


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.application.bot_data["cfg"]
    user = update.effective_user
    if not user or not _is_allowed(cfg, user.id):
        return
    await update.message.reply_text("Send a contact photo or use /health.")


def _safe_proxy_display(url: str) -> str:
    if not url:
        return "(none)"
    try:
        p = urlparse(url)
        host = p.hostname or "?"
        port = f":{p.port}" if p.port else ""
        return f"{p.scheme}://{host}{port}"
    except Exception:
        return "(set)"


def build_application(cfg: Config) -> Application:
    builder: ApplicationBuilder = (
        Application.builder()
        .token(cfg.telegram_bot_token)
        .connect_timeout(cfg.telegram_connect_timeout)
        .read_timeout(cfg.telegram_read_timeout)
        .write_timeout(cfg.telegram_write_timeout)
        .pool_timeout(cfg.telegram_pool_timeout)
        .get_updates_connect_timeout(cfg.telegram_connect_timeout)
        .get_updates_read_timeout(cfg.telegram_read_timeout)
        .get_updates_write_timeout(cfg.telegram_write_timeout)
        .get_updates_pool_timeout(cfg.telegram_pool_timeout)
    )
    if cfg.telegram_proxy_url:
        builder = builder.proxy(cfg.telegram_proxy_url)
    if cfg.telegram_get_updates_proxy_url:
        builder = builder.get_updates_proxy(cfg.telegram_get_updates_proxy_url)

    app = builder.build()
    app.bot_data["cfg"] = cfg
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(
        MessageHandler(filters.Document.IMAGE, handle_image)
    )
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_unknown))
    return app


def main() -> None:
    cfg = load_config()
    if not cfg.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    if not cfg.allowed_user_ids:
        log.warning(
            "TELEGRAM_ALLOWED_USER_IDS is empty — the bot will reject ALL users. "
            "Set the list of IDs in .env."
        )
    log.info(
        "Starting bot. allowlist=%d users, my_endpoints=%s, model=%s",
        len(cfg.allowed_user_ids),
        cfg.my_endpoints_base_url or "(not set)",
        cfg.openrouter_model or "(not set)",
    )
    log.info(
        "Telegram timeouts: connect=%.1fs read=%.1fs write=%.1fs pool=%.1fs; "
        "proxy=%s; get_updates_proxy=%s",
        cfg.telegram_connect_timeout,
        cfg.telegram_read_timeout,
        cfg.telegram_write_timeout,
        cfg.telegram_pool_timeout,
        _safe_proxy_display(cfg.telegram_proxy_url),
        _safe_proxy_display(cfg.telegram_get_updates_proxy_url),
    )

    delay = max(1.0, cfg.telegram_startup_retry_delay)
    attempt = 0
    while True:
        attempt += 1
        try:
            app = build_application(cfg)
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                bootstrap_retries=-1,
            )
            return
        except (TimedOut, NetworkError) as e:
            log.error(
                "Startup network error (attempt %d): %s. "
                "Retrying in %.0f s. "
                "Check VPS DNS / Telegram API reachability / TELEGRAM_PROXY_URL.",
                attempt,
                e,
                delay,
            )
            time.sleep(delay)
        except KeyboardInterrupt:
            log.info("Interrupted, exiting.")
            return


if __name__ == "__main__":
    main()
