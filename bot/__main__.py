import asyncio
import logging
import signal
import sys

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

    history = ConversationHistory(config.history_limit)
    models = ModelManager(config.default_model)
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

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(bot, api, dp)))

    await dp.start_polling(
        bot,
        config=config,
        history=history,
        models=models,
        api=api,
    )


async def shutdown(bot: Bot, api: FreeDeepseekClient, dp: Dispatcher):
    logger.info("Shutting down...")
    await dp.stop_polling()
    await api.close()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
