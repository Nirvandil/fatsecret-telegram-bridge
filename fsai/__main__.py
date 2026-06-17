"""Точка входа: python -m fsai — запускает бота в режиме long-polling."""
import asyncio
import logging

from dotenv import load_dotenv

from fsai.bot import TelegramBot
from fsai.config import load_config
from fsai.fatsecret_client import FatSecretClient
from fsai.llm.factory import build_provider
from fsai.service import LoggerService
from fsai.store import Store

logger = logging.getLogger("fsai")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # HTTP-клиент логирует каждый getUpdates-поллинг — это шум, глушим до WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()
    config = load_config()
    _setup_logging(config.log_level)
    logger.info("LLM-провайдер: %s (%s)", config.llm_provider, config.llm_model)

    provider = build_provider(config)
    client = FatSecretClient(
        config.fatsecret_consumer_key, config.fatsecret_consumer_secret,
        config.fatsecret_access_token, config.fatsecret_access_secret,
    )
    store = Store(config.db_path)
    service = LoggerService(
        provider=provider, client=client, store=store,
        meal_bounds=(config.meal_breakfast_start, config.meal_lunch_start,
                     config.meal_dinner_start, config.meal_dinner_end),
    )
    bot = TelegramBot(config, service)
    app = bot.build_application()

    # Python 3.14: asyncio.get_event_loop() больше не создаёт цикл сам, а
    # python-telegram-bot v21 в run_polling() на это рассчитывает. Создаём явно.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    logger.info(
        "fsai запущен (long-polling: timeout=%ss, poll_interval=%ss, owner=%s). "
        "Останов — Ctrl+C.",
        config.poll_timeout, config.poll_interval, config.owner_chat_id,
    )
    app.run_polling(
        poll_interval=config.poll_interval,
        timeout=config.poll_timeout,
    )


if __name__ == "__main__":
    main()
