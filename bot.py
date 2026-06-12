import asyncio
import json
import os
import time
from typing import Dict, List

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELOXIDE_TOKEN")
API_URL = os.getenv("DEEPSEEK_API_URL", "http://localhost:9655/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-chat")

if not TOKEN:
    raise SystemExit("TELOXIDE_TOKEN is not set in .env")

MAX_HISTORY = 20

# --- Conversation History ---

history: Dict[int, List[dict]] = {}


def add_message(chat_id: int, role: str, content: str):
    if chat_id not in history:
        history[chat_id] = []
    history[chat_id].append({"role": role, "content": content})
    if len(history[chat_id]) > MAX_HISTORY:
        history[chat_id] = history[chat_id][-MAX_HISTORY:]


def get_history(chat_id: int) -> List[dict]:
    return history.get(chat_id, [])


def clear_history(chat_id: int):
    history.pop(chat_id, None)


# --- Model Selection ---

user_model: Dict[int, str] = {}


def get_model(chat_id: int) -> str:
    return user_model.get(chat_id, DEFAULT_MODEL)


def set_model(chat_id: int, model: str):
    user_model[chat_id] = model


# --- Keyboard ---

def model_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    models = [
        ("📝 deepseek-chat", "model:deepseek-chat"),
        ("🧠 deepseek-reasoner", "model:deepseek-reasoner"),
        ("🌐 deepseek-chat-search", "model:deepseek-chat-search"),
        ("🔬 deepseek-expert", "model:deepseek-expert"),
        ("🧪 deepseek-v4-pro", "model:deepseek-v4-pro"),
    ]
    for label, data in models:
        kb.button(text=label, callback_data=data)
    kb.adjust(1)
    return kb.as_markup()


# --- Bot ---

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- Commands ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я DeepSeek бот на Python.\n\n"
        "Отправь мне любой вопрос, и я отвечу через DeepSeek AI.\n\n"
        "Доступные команды:\n"
        "/help — помощь\n"
        "/reset — сбросить историю диалога\n"
        "/model — выбрать модель"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 Доступные команды:\n"
        "/start — начать\n"
        "/help — эта справка\n"
        "/reset — сбросить историю диалога\n"
        "/model — выбрать модель AI\n\n"
        "💡 Просто отправьте сообщение, чтобы начать диалог."
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    clear_history(message.chat.id)
    await message.answer("✅ История диалога сброшена.")


@dp.message(Command("model"))
async def cmd_model(message: Message):
    current = get_model(message.chat.id)
    await message.answer(
        f"🤖 Выберите модель (текущая: {current}):",
        reply_markup=model_keyboard(),
    )


# --- Callback ---

@dp.callback_query(F.data.startswith("model:"))
async def cb_model(query: CallbackQuery):
    model = query.data[6:]
    chat_id = query.message.chat.id if query.message else query.from_user.id
    set_model(chat_id, model)
    await query.answer()

    escaped = model.replace("_", "\\_").replace("-", "\\-").replace(".", "\\.")
    text = f"✅ Модель: `{escaped}`"
    if query.message:
        await query.message.edit_text(text, parse_mode="MarkdownV2")


# --- Messages ---

@dp.message(F.text)
async def handle_message(message: Message):
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    text = message.text.strip()

    if not text:
        return

    add_message(chat_id, "user", text)

    model = get_model(chat_id)
    msgs = get_history(chat_id)

    sent = await message.answer("⏳ Думаю...")

    body = {
        "model": model,
        "messages": msgs,
        "stream": True,
    }

    accumulated = ""
    last_edit = 0.0
    error = None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", f"{API_URL}/chat/completions", json=body
            ) as resp:
                if resp.status_code != 200:
                    err_text = await resp.aread()
                    error = f"API error {resp.status_code}"
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        for choice in chunk.get("choices", []):
                            content = choice.get("delta", {}).get("content", "")
                            if content:
                                accumulated += content
                                now = time.monotonic()
                                if now - last_edit >= 0.4:
                                    display = truncate_text(accumulated, 4000)
                                    try:
                                        await sent.edit_text(display)
                                    except Exception:
                                        pass
                                    last_edit = now
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        error = str(e)

    if error:
        try:
            await sent.edit_text(f"⚠️ Ошибка: {error}")
        except Exception:
            pass
        return

    if not accumulated:
        try:
            await sent.edit_text("⚠️ Получен пустой ответ от API. Попробуйте позже.")
        except Exception:
            pass
        return

    display = truncate_text(accumulated, 4096)
    try:
        await sent.edit_text(display)
    except Exception:
        pass

    add_message(chat_id, "assistant", accumulated)


# --- Helpers ---

def truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 20] + "\n\n... ✂️ сокращено"


# --- Main ---

async def main():
    print(f"Bot started. URL: {API_URL}, default model: {DEFAULT_MODEL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
