from __future__ import annotations

import asyncio
import base64
import datetime
import fnmatch
import os
import time

import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from db import Database
from i18n import get_lang, t
from markdown_conv import md_to_chunks
from provider import ChatStream, ProviderError, chat_once, list_models
from settings import (
    DB_PATH,
    STREAM_UPDATE_INTERVAL_SEC,
    TELEGRAM_BOT_TOKEN,
)
from telegram_stream import StreamTarget, TelegramStreamer


db = Database(DB_PATH)

_DELETE_DELAY = 60.0  # seconds before system messages are auto-deleted


def _fmt_date(ts: int, lang: str) -> str:
    diff = time.time() - ts
    if diff < 86400:
        return t("date_today", lang)
    if diff < 172800:
        return t("date_yesterday", lang)
    return datetime.datetime.fromtimestamp(ts).strftime("%b %d")


def _session_keyboards(
    sessions: list[dict],
    current_id: int | None,
    action: str,
    lang: str,
) -> InlineKeyboardMarkup:
    """Build an inline keyboard listing sessions for resume/del actions."""
    rows = []
    for s in sessions:
        title = s["title"][:24]
        date = _fmt_date(s["updated_at"], lang)
        star = " ★" if s["session_id"] == current_id else ""
        label = f"{title} ({date}){star}"
        rows.append([InlineKeyboardButton(label, callback_data=f"sess:{action}:{s['session_id']}")])
    return InlineKeyboardMarkup(rows)


# ── Auto-delete helpers ───────────────────────────────────────────────────────

async def _autodelete(bot, chat_id: int, message_id: int, delay: float = _DELETE_DELAY) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    delay: float = _DELETE_DELAY,
    **kwargs,
) -> None:
    """Reply to update.message and schedule auto-deletion after delay seconds."""
    msg = await update.message.reply_text(text, **kwargs)
    asyncio.create_task(_autodelete(context.bot, update.effective_chat.id, msg.message_id, delay))


def _schedule_delete(bot, chat_id: int, message_id: int, delay: float = _DELETE_DELAY) -> None:
    asyncio.create_task(_autodelete(bot, chat_id, message_id, delay))


# ── Config commands ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_lang(update.effective_user)
    await _reply(update, context, t("help", lang))


async def command_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    value = " ".join(context.args).strip() if context.args else ""
    if value:
        await db.set_field(update.effective_user.id, "provider", value)
        await _reply(update, context, t("provider_updated", lang))
        return
    user = await db.get_user(update.effective_user.id)
    current = user["provider"]
    if current:
        await _reply(update, context, t("provider_current", lang, url=current))
    else:
        await _reply(update, context, t("provider_not_set", lang))


async def command_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    value = " ".join(context.args).strip() if context.args else ""
    if value:
        await db.set_field(update.effective_user.id, "apikey", value)
        await _reply(update, context, t("apikey_updated", lang))
        return
    user = await db.get_user(update.effective_user.id)
    current = user["apikey"]
    if current:
        masked = current[:4] + "..." + current[-4:] if len(current) > 8 else "****"
        await _reply(update, context, t("apikey_current", lang, masked=masked))
    else:
        await _reply(update, context, t("apikey_not_set", lang))


async def command_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    value = " ".join(context.args).strip() if context.args else ""
    if value:
        await db.set_field(update.effective_user.id, "model", value)
        await _reply(update, context, t("model_updated", lang, model=value))
        return
    user = await db.get_user(update.effective_user.id)
    current = user["model"]
    if current:
        await _reply(update, context, t("model_current", lang, model=current))
    else:
        await _reply(update, context, t("model_not_set", lang))


async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    lang = get_lang(query.from_user)
    model = query.data.split(":", 1)[1]
    await db.set_field(query.from_user.id, "model", model)
    await query.edit_message_text(text=t("model_updated", lang, model=model))
    _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)


_ML_PAGE_SIZE = 20


def _modellist_keyboard(
    models: list[str], current_model: str, page: int, lang: str
) -> InlineKeyboardMarkup:
    start = page * _ML_PAGE_SIZE
    page_models = models[start : start + _ML_PAGE_SIZE]
    rows = []
    for i, m in enumerate(page_models):
        label = f"{'★ ' if m == current_model else ''}{m}"
        rows.append([InlineKeyboardButton(label, callback_data=f"ml:s:{start + i}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(t("btn_prev", lang), callback_data=f"ml:p:{page - 1}"))
    if start + _ML_PAGE_SIZE < len(models):
        nav.append(InlineKeyboardButton(t("btn_next", lang), callback_data=f"ml:p:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def command_modellist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if not user["provider"]:
        await _reply(update, context, t("modellist_no_provider", lang))
        return

    pattern = " ".join(context.args).strip().lower() if context.args else ""

    try:
        http_session: aiohttp.ClientSession = context.application.bot_data["session"]
        models = await list_models(http_session, base_url=user["provider"], api_key=user["apikey"])
    except ProviderError as exc:
        await _reply(update, context, str(exc))
        return
    except Exception as exc:
        await _reply(update, context, t("modellist_fetch_failed", lang, error=exc))
        return

    if pattern:
        models = [m for m in models if fnmatch.fnmatch(m.lower(), f"*{pattern}*")]

    if not models:
        msg = (
            t("modellist_no_match", lang, pattern=pattern)
            if pattern
            else t("modellist_empty", lang)
        )
        await _reply(update, context, msg)
        return

    # Store list in user_data so page callbacks can reference it by index
    context.user_data["ml_models"] = models
    context.user_data["ml_pattern"] = pattern

    current_model = user["model"] or ""
    total = len(models)
    header = (
        t("modellist_header_filtered", lang, pattern=pattern, total=total)
        if pattern
        else t("modellist_header", lang, total=total)
    )
    await _reply(
        update, context, header,
        reply_markup=_modellist_keyboard(models, current_model, 0, lang),
    )


async def modellist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    lang = get_lang(query.from_user)

    parts = query.data.split(":", 2)
    action = parts[1]
    user_id = query.from_user.id
    models: list[str] = context.user_data.get("ml_models", [])

    if not models:
        await query.edit_message_text(t("modellist_expired", lang))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)
        return

    if action == "s":
        idx = int(parts[2])
        if idx >= len(models):
            await query.edit_message_text(t("modellist_expired", lang))
            _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)
            return
        model = models[idx]
        await db.set_field(user_id, "model", model)
        await query.edit_message_text(t("model_updated", lang, model=model))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)

    elif action == "p":
        page = int(parts[2])
        user = await db.get_user(user_id)
        current_model = user["model"] or ""
        pattern = context.user_data.get("ml_pattern", "")
        total = len(models)
        header = (
            t("modellist_header_filtered", lang, pattern=pattern, total=total)
            if pattern
            else t("modellist_header", lang, total=total)
        )
        await query.edit_message_text(
            header, reply_markup=_modellist_keyboard(models, current_model, page, lang)
        )
        # Keep alive while paginating — no delete scheduled here


# ── Session commands ─────────────────────────────────────────────────────────

async def command_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    session_id = await db.create_session(update.effective_user.id)
    await _reply(update, context, t("session_new", lang, id=session_id))


async def command_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if user["current_session_id"] is not None:
        await db.delete_session(user["current_session_id"])
    session_id = await db.create_session(user_id)
    await _reply(update, context, t("session_cleared", lang, id=session_id))


async def command_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id
    sessions = await db.get_sessions(user_id)
    if not sessions:
        await _reply(update, context, t("session_none", lang))
        return
    user = await db.get_user(user_id)
    keyboard = _session_keyboards(sessions, user["current_session_id"], "resume", lang)
    await _reply(update, context, t("session_choose_resume", lang), reply_markup=keyboard)


async def command_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id
    sessions = await db.get_sessions(user_id)
    if not sessions:
        await _reply(update, context, t("session_none_to_delete", lang))
        return
    user = await db.get_user(user_id)
    keyboard = _session_keyboards(sessions, user["current_session_id"], "del", lang)
    await _reply(update, context, t("session_choose_delete", lang), reply_markup=keyboard)


async def session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    lang = get_lang(query.from_user)

    parts = query.data.split(":", 2)
    if len(parts) != 3:
        return
    _, action, sid_str = parts
    session_id = int(sid_str)
    user_id = query.from_user.id

    session = await db.get_session(session_id)
    if not session or session["user_id"] != user_id:
        await query.edit_message_text(t("session_not_found", lang))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)
        return

    if action == "resume":
        await db.set_field(user_id, "current_session_id", session_id)
        await query.edit_message_text(t("session_resumed", lang, title=session["title"]))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)

    elif action == "del":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(t("btn_yes_delete", lang), callback_data=f"sess:del_confirm:{session_id}"),
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="sess:cancel:0"),
        ]])
        await query.edit_message_text(
            t("session_confirm_delete", lang, title=session["title"]),
            reply_markup=keyboard,
        )
        # Keep alive while waiting for confirm/cancel — no delete scheduled here

    elif action == "del_confirm":
        title = session["title"]
        await db.delete_session(session_id)
        await query.edit_message_text(t("session_deleted", lang, title=title))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)

    elif action == "cancel":
        await query.edit_message_text(t("session_cancelled", lang))
        _schedule_delete(context.bot, query.message.chat.id, query.message.message_id)


# ── Shared chat logic ─────────────────────────────────────────────────────────

async def _run_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    messages: list[dict],
    session_id: int,
    lang: str,
    user_text_for_db: str,
) -> None:
    """Stream a chat request and persist the result. Shared by text and photo handlers."""
    user = await db.get_user(update.effective_user.id)
    provider = user["provider"]
    model = user["model"]
    apikey = user["apikey"]

    chat = update.effective_chat
    target = StreamTarget(
        chat_id=chat.id,
        message_thread_id=getattr(update.message, "message_thread_id", None),
        can_use_draft=True,  # Available to all bots since Bot API 9.5
    )

    streamer: TelegramStreamer = context.application.bot_data["streamer"]
    http_session: aiohttp.ClientSession = context.application.bot_data["session"]

    final_text: str
    usage: dict | None = None

    try:
        chat_stream = ChatStream(
            http_session,
            base_url=provider,
            api_key=apikey,
            model=model,
            messages=messages,
        )
        final_text = await streamer.stream_text(
            target=target,
            text_stream=chat_stream,
            update_interval=STREAM_UPDATE_INTERVAL_SEC,
            empty_response=t("empty_response", lang),
        )
        usage = chat_stream.usage
    except ProviderError as exc:
        await _reply(update, context, str(exc))
        return
    except aiohttp.InvalidURL:
        await _reply(update, context, t("chat_invalid_url", lang))
        return
    except aiohttp.ClientConnectorError as exc:
        await _reply(update, context, t("chat_connect_error", lang, error=exc.os_error))
        return
    except Exception:
        # Streaming failed — fall back to non-streaming
        try:
            final_text, usage = await chat_once(
                http_session,
                base_url=provider,
                api_key=apikey,
                model=model,
                messages=messages,
            )
            for text, pm in md_to_chunks(final_text):
                await update.message.reply_text(text, parse_mode=pm)
        except ProviderError as exc:
            await _reply(update, context, str(exc))
            return
        except Exception as exc:
            await _reply(update, context, t("chat_request_failed", lang, error=exc))
            return

    # Persist the exchange
    total_tokens = int(usage.get("total_tokens", 0)) if usage else 0
    await db.add_message(session_id, "user", user_text_for_db)
    await db.add_message(session_id, "assistant", final_text, tokens=total_tokens)

    # Session token summary footer (auto-deletes)
    session_tokens = await db.get_session_tokens(session_id)
    session_info = await db.get_session(session_id)
    title_short = (session_info["title"] or "Session")[:25] if session_info else "Session"
    msg = await update.message.reply_text(
        t("token_footer", lang, title=title_short, tokens=f"{session_tokens:,}"),
        disable_notification=True,
    )
    _schedule_delete(context.bot, update.effective_chat.id, msg.message_id)


# ── Message handlers ──────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id

    user = await db.get_user(user_id)
    if not user["provider"]:
        await _reply(update, context, t("chat_no_provider", lang))
        return
    if not user["model"]:
        await _reply(update, context, t("chat_no_model", lang))
        return

    # Resolve current session (create one if needed or if it was deleted)
    session_id = user["current_session_id"]
    if session_id is not None and await db.get_session(session_id) is None:
        session_id = None
    if session_id is None:
        session_id = await db.create_session(user_id)

    # Auto-title from the first message in this session
    history = await db.get_messages(session_id)
    if not history:
        title = update.message.text[:40].replace("\n", " ")
        await db.set_session_title(session_id, title)

    messages = history + [{"role": "user", "content": update.message.text}]
    await _run_chat(update, context, messages, session_id, lang, update.message.text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return
    lang = get_lang(update.effective_user)
    user_id = update.effective_user.id

    user = await db.get_user(user_id)
    if not user["provider"]:
        await _reply(update, context, t("chat_no_provider", lang))
        return
    if not user["model"]:
        await _reply(update, context, t("chat_no_model", lang))
        return

    # Resolve current session
    session_id = user["current_session_id"]
    if session_id is not None and await db.get_session(session_id) is None:
        session_id = None
    if session_id is None:
        session_id = await db.create_session(user_id)

    # Download the largest photo size and base64-encode it
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    photo_bytes = await photo_file.download_as_bytearray()
    b64 = base64.b64encode(photo_bytes).decode()

    caption = (update.message.caption or "").strip()
    user_text = caption if caption else t("image_no_caption", lang)

    # Auto-title from the first message in this session
    history = await db.get_messages(session_id)
    if not history:
        title = (caption or t("image_label", lang))[:40].replace("\n", " ")
        await db.set_session_title(session_id, title)

    # Build vision-compatible message (OpenAI image_url format)
    image_message: dict = {
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ],
    }
    messages = history + [image_message]
    await _run_chat(update, context, messages, session_id, lang, user_text)


# ── App lifecycle ────────────────────────────────────────────────────────────

async def on_startup(app: Application) -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    await db.connect()
    session = aiohttp.ClientSession()
    app.bot_data["session"] = session
    app.bot_data["streamer"] = TelegramStreamer(
        bot=app.bot,
        token=TELEGRAM_BOT_TOKEN,
        session=session,
    )


async def on_shutdown(app: Application) -> None:
    session: aiohttp.ClientSession = app.bot_data.get("session")
    if session:
        await session.close()
    await db.close()


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("provider", command_provider))
    application.add_handler(CommandHandler("apikey", command_apikey))
    application.add_handler(CommandHandler("model", command_model))
    application.add_handler(CommandHandler("modellist", command_modellist))
    application.add_handler(CommandHandler("new", command_new))
    application.add_handler(CommandHandler("clear", command_clear))
    application.add_handler(CommandHandler("resume", command_resume))
    application.add_handler(CommandHandler("del", command_del))

    application.add_handler(CallbackQueryHandler(model_callback, pattern="^model:"))
    application.add_handler(CallbackQueryHandler(modellist_callback, pattern="^ml:"))
    application.add_handler(CallbackQueryHandler(session_callback, pattern="^sess:"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    application.post_init = on_startup
    application.post_shutdown = on_shutdown

    application.run_polling()


if __name__ == "__main__":
    main()
