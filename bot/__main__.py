import asyncio
import logging
import sys

import aiosqlite

from aiogram import Bot, Dispatcher

from .api import FreeDeepseekClient
from .config import Config
from .handlers import router
from .storage import ConversationHistory, ModelManager

logger = logging.getLogger(__name__)


async def main():
    config = Config()

    if not config.telegram_token:
        sys.exit("TELOXIDE_TOKEN is not set in .env")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )

    bot = Bot(token=config.telegram_token)

    db = await aiosqlite.connect(config.db_path)
    db.row_factory = aiosqlite.Row

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS model_preferences (
            chat_id INTEGER PRIMARY KEY,
            model TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_chat
        ON conversations(chat_id)
    """)
    await db.commit()

    history = ConversationHistory(db, config.history_limit)
    models = ModelManager(db, config.default_model)
    api = FreeDeepseekClient(
        config.api_url,
        timeout=config.api_timeout,
        connect_timeout=config.api_connect_timeout,
    )

    dp = Dispatcher()
    dp.include_router(router)

    logger.info(
        "Bot starting | API: %s | default model: %s",
        config.api_url,
        config.default_model,
    )

    try:
        await dp.start_polling(
            bot,
            config=config,
            history=history,
            models=models,
            api=api,
        )
    finally:
        logger.info("Shutting down...")
        await api.close()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
