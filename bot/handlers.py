import asyncio
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from . import keyboards
from .api import FreeDeepseekClient, FreeDeepseekError
from .config import Config
from .storage import ConversationHistory, ModelManager

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, config: Config):
    await message.answer(
        "👋 Привет! Я DeepSeek бот.\n\n"
        "Отправь мне вопрос, и я отвечу через DeepSeek AI.\n\n"
        "Команды:\n"
        "/help — помощь\n"
        "/reset — сбросить историю\n"
        "/model — выбрать модель"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/start — начать\n"
        "/help — помощь\n"
        "/reset — сбросить историю\n"
        "/model — выбрать модель\n\n"
        "💡 Отправьте сообщение для диалога."
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, history: ConversationHistory):
    count = await history.clear(message.chat.id)
    await message.answer(f"✅ История сброшена (удалено {count} сообщений).")


@router.message(Command("model"))
async def cmd_model(message: Message, models: ModelManager):
    current = await models.get(message.chat.id)
    await message.answer(
        f"🤖 Выберите модель (текущая: {current}):",
        reply_markup=keyboards.model_keyboard(),
    )


@router.callback_query(F.data.startswith("model:"))
async def cb_model(query: CallbackQuery, models: ModelManager):
    model = query.data[6:]
    chat_id = query.message.chat.id if query.message else query.from_user.id
    await models.set(chat_id, model)
    await query.answer()

    escaped = model.replace("_", "\\_").replace("-", "\\-").replace(".", "\\.")
    text = f"✅ Модель: `{escaped}`"
    if query.message:
        await query.message.edit_text(text, parse_mode="MarkdownV2")


@router.message(F.text)
async def handle_message(
    message: Message,
    history: ConversationHistory,
    models: ModelManager,
    api: FreeDeepseekClient,
    config: Config,
):
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    text = message.text.strip()
    if not text:
        return

    await history.add(chat_id, "user", text)

    model = await models.get(chat_id)
    msgs = await history.get(chat_id)

    sent = await message.answer("⏳ Думаю...")

    accumulated = ""
    last_edit = 0.0
    error = None

    try:
        async with asyncio.timeout(config.api_timeout):
            async for chunk in api.stream_chat(model, msgs):
                accumulated += chunk
                now = time.monotonic()
                if now - last_edit >= config.edit_interval:
                    try:
                        await sent.edit_text(accumulated[: config.max_message_length])
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
    try:
        await sent.edit_text(full, parse_mode="MarkdownV2")
    except TelegramBadRequest:
        try:
            await sent.edit_text(full)
        except Exception:
            pass
    except Exception:
        try:
            await sent.edit_text(full)
        except Exception:
            pass

    await history.add(chat_id, "assistant", accumulated)
