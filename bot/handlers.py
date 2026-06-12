import asyncio
import logging
import re
import time

import io

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from . import keyboards
from .api import FreeDeepseekClient, FreeDeepseekError
from .config import Config
from .storage import ChatMessage, ConversationHistory, ModelManager, SessionManager

logger = logging.getLogger(__name__)

router = Router()


_BLOCK_PATTERNS = [
    (r'```([\s\S]*?)```', r'\1'),
    (r'`([^`]+)`', r'\1'),
    (r'\*\*\*(.+?)\*\*\*', r'\1'),
    (r'\*\*(.+?)\*\*', r'\1'),
    (r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1'),
    (r'~~(.+?)~~', r'\1'),
    (r'^#{1,6}\s+', '', re.MULTILINE),
    (r'^[-*_]{3,}\s*$', '', re.MULTILINE),
    (r'^[-*+]\s+', '', re.MULTILINE),
    (r'^\d+\.\s+', '', re.MULTILINE),
    (r'^>\s?', '', re.MULTILINE),
]


def strip_markdown(text: str) -> str:
    for pat_info in _BLOCK_PATTERNS:
        pat, repl, *flags = pat_info
        kwargs = {}
        if flags:
            kwargs["flags"] = flags[0]
        text = re.sub(pat, repl, text, **kwargs)
    return text


def _pre(text: str) -> str:
    return f'<pre>{text.strip()}</pre>' if text.strip() else ""


def markdown_to_html(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    text = re.sub(r'```(.*?)```', lambda m: _pre(m.group(1)), text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)

    return text


async def _stream_response(
    message: Message,
    api: FreeDeepseekClient,
    sessions: SessionManager,
    history: ConversationHistory,
    model: str,
    chat_id: int,
    user_display_text: str,
    api_messages: list[ChatMessage],
    config: Config,
):
    await history.add(chat_id, "user", user_display_text)

    session_id = await sessions.get_or_create(chat_id)
    logger.debug(
        "Chat %s: streaming to model %s (session=%s)",
        chat_id, model, session_id,
    )

    sent = await message.answer("⏳ Думаю...")

    accumulated = ""
    last_edit = 0.0
    error = None

    try:
        async with asyncio.timeout(config.api_timeout):
            async for chunk in api.stream_chat(session_id, model, api_messages):
                accumulated += chunk
                now = time.monotonic()
                if now - last_edit >= config.edit_interval:
                    try:
                        clean = strip_markdown(accumulated[: config.max_message_length])
                        await sent.edit_text(clean)
                    except TelegramBadRequest:
                        pass
                    except Exception:
                        pass
                    last_edit = now
    except FreeDeepseekError as e:
        error = f"Ошибка API ({e.status})"
        logger.error("Chat error chat=%s status=%s detail=%s", chat_id, e.status, e.detail)
    except TimeoutError:
        error = "Таймаут ожидания ответа от DeepSeek"
    except Exception as e:
        error = str(e)
        logger.exception("Unexpected error chat=%s", chat_id)

    if error:
        try:
            await sent.edit_text(f"⚠️ {error}")
        except Exception:
            pass
        return

    if not accumulated:
        try:
            await sent.edit_text("⚠️ Получен пустой ответ.")
        except Exception:
            pass
        return

    full = accumulated[: config.max_message_length]

    html = markdown_to_html(full)
    try:
        await sent.edit_text(html, parse_mode="HTML")
        logger.debug("Final edit: HTML ok (%d chars)", len(full))
    except TelegramBadRequest as e:
        logger.debug("HTML failed: %s; trying stripped", e)
        cleaned = strip_markdown(full)
        try:
            await sent.edit_text(cleaned)
            logger.debug("Final edit: stripped fallback (%d chars)", len(cleaned))
        except Exception:
            try:
                await sent.edit_text(full)
                logger.debug("Final edit: plain fallback (%d chars)", len(full))
            except Exception:
                pass
    except Exception:
        try:
            await sent.edit_text(full)
        except Exception:
            pass

    await history.add(chat_id, "assistant", accumulated)


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я DeepSeek бот.\n\n"
        "Отправь мне вопрос, и я отвечу через DeepSeek AI.\n\n"
        "Команды:\n"
        "/help — помощь\n"
        "/new_chat — новый чат\n"
        "/model — выбрать модель\n\n"
        "📷 Поддерживаются фото и документы."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/start — начать\n"
        "/help — помощь\n"
        "/new_chat — новый чат (сброс контекста DeepSeek)\n"
        "/model — выбрать модель\n\n"
        "💡 Отправьте сообщение для диалога.\n"
        "📷 Отправьте фото с подписью для анализа изображения.\n"
        "📎 Отправьте текстовый файл для анализа содержимого."
    )


@router.message(Command("new_chat"))
async def cmd_new_chat(
    message: Message,
    history: ConversationHistory,
    sessions: SessionManager,
):
    chat_id = message.chat.id
    await sessions.rotate(chat_id)
    await history.clear(chat_id)
    logger.info("New chat for %s, session rotated", chat_id)
    await message.answer("🆕 Создан новый чат. История очищена.")


@router.message(Command("chat_id"))
async def cmd_chat_id(message: Message):
    await message.answer(
        f"🆔 ID этого чата: `{message.chat.id}`\n"
        f"👤 Ваш ID: `{message.from_user.id if message.from_user else '?'}`"
    )


@router.message(Command("model"))
async def cmd_model(message: Message, models: ModelManager):
    current = await models.get(message.chat.id)
    await message.answer(
        f"🤖 Выберите модель (текущая: {current}):",
        reply_markup=keyboards.model_keyboard(),
    )


@router.callback_query(F.data.startswith("model:"))
async def cb_model(
    query: CallbackQuery,
    models: ModelManager,
    history: ConversationHistory,
    sessions: SessionManager,
):
    model = query.data[6:]
    chat_id = query.message.chat.id if query.message else query.from_user.id
    await models.set(chat_id, model)
    await sessions.rotate(chat_id)
    await history.clear(chat_id)
    logger.info("Model set for chat %s: %s, session rotated", chat_id, model)
    await query.answer()

    text = f"✅ Модель: {model}\n🆕 Создан новый чат."
    if query.message:
        await query.message.edit_text(text)


@router.message(F.text)
async def handle_message(
    message: Message,
    history: ConversationHistory,
    models: ModelManager,
    api: FreeDeepseekClient,
    sessions: SessionManager,
    config: Config,
):
    if message.text.startswith("/"):
        return

    text = message.text.strip()
    if not text:
        return

    chat_id = message.chat.id
    model = await models.get(chat_id)

    await _stream_response(
        message, api, sessions, history, model, chat_id,
        user_display_text=text,
        api_messages=[ChatMessage("user", text)],
        config=config,
    )


@router.message(F.photo)
async def handle_photo(
    message: Message,
    history: ConversationHistory,
    models: ModelManager,
    api: FreeDeepseekClient,
    sessions: SessionManager,
    config: Config,
):
    chat_id = message.chat.id
    caption = (message.caption or "").strip()
    if not caption:
        await message.answer("📷 Пожалуйста, добавьте текстовое описание к фото.")
        return
    model = await models.get(chat_id)
    await _stream_response(
        message, api, sessions, history, model, chat_id,
        user_display_text=caption,
        api_messages=[ChatMessage("user", caption)],
        config=config,
    )


@router.message(F.document)
async def handle_document(
    message: Message,
    history: ConversationHistory,
    models: ModelManager,
    api: FreeDeepseekClient,
    sessions: SessionManager,
    config: Config,
):
    chat_id = message.chat.id
    doc = message.document
    mime = doc.mime_type or ""
    caption = (message.caption or "").strip()
    model = await models.get(chat_id)

    if mime.startswith("image/"):
        if not caption:
            await message.answer("📷 Пожалуйста, добавьте текстовое описание к изображению.")
            return
        await _stream_response(
            message, api, sessions, history, model, chat_id,
            user_display_text=caption,
            api_messages=[ChatMessage("user", caption)],
            config=config,
        )
    elif mime.startswith("text/") or mime in (
        "application/json", "application/xml", "application/javascript",
        "application/x-python-code",
    ):
        file = await message.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await message.bot.download(file, destination=buf)
        text = buf.getvalue().decode("utf-8", errors="replace")
        full_text = f"{caption}\n\n```\n{text[:4000]}\n```" if caption else f"```\n{text[:4000]}\n```"
        user_text = caption or f"[файл: {doc.file_name}]"
        await _stream_response(
            message, api, sessions, history, model, chat_id,
            user_display_text=user_text,
            api_messages=[ChatMessage("user", full_text)],
            config=config,
        )
    else:
        meta = f"Файл: {doc.file_name or 'unknown'}"
        if doc.file_size:
            size_kb = doc.file_size / 1024
            meta += f" ({size_kb:.0f} KB)"
        user_text = caption or meta
        await _stream_response(
            message, api, sessions, history, model, chat_id,
            user_display_text=user_text,
            api_messages=[ChatMessage("user", user_text)],
            config=config,
        )
