from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

MODELS = [
    ("📝 deepseek-chat", "model:deepseek-chat"),
    ("🧠 deepseek-reasoner", "model:deepseek-reasoner"),
    ("🌐 deepseek-chat-search", "model:deepseek-chat-search"),
    ("🔬 deepseek-expert", "model:deepseek-expert"),
    ("🧪 deepseek-v4-pro", "model:deepseek-v4-pro"),
]


def model_keyboard(current: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for label, data in MODELS:
        kb.button(text=label, callback_data=data)
    kb.adjust(1)
    return kb.as_markup()
