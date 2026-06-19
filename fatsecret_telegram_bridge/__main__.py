"""Entry point: python -m fatsecret_telegram_bridge — runs the bot in long-polling mode."""
import asyncio
import logging

from dotenv import load_dotenv

from fatsecret_telegram_bridge.bot import TelegramBot
from fatsecret_telegram_bridge.config import load_config
from fatsecret_telegram_bridge.fatsecret_client import FatSecretClient
from fatsecret_telegram_bridge.llm.factory import build_provider
from fatsecret_telegram_bridge.service import LoggerService
from fatsecret_telegram_bridge.store import Store

logger = logging.getLogger("fatsecret_telegram_bridge")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # The HTTP client logs every getUpdates poll — that's noise, quiet it to WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    load_dotenv()
    config = load_config()
    _setup_logging(config.log_level)
    logger.info("LLM provider: %s (%s)", config.llm_provider, config.llm_model)

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

    # Python 3.14: asyncio.get_event_loop() no longer creates a loop itself, but
    # python-telegram-bot v21's run_polling() relies on that. Create one explicitly.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    logger.info(
        "fatsecret_telegram_bridge started (long-polling: timeout=%ss, "
        "poll_interval=%ss, owner=%s). Stop with Ctrl+C.",
        config.poll_timeout, config.poll_interval, config.owner_chat_id,
    )
    app.run_polling(
        poll_interval=config.poll_interval,
        timeout=config.poll_timeout,
    )


if __name__ == "__main__":
    main()
