"""Точка входа: python -m fsai — запускает бота в режиме long-polling."""
from dotenv import load_dotenv

from fsai.bot import TelegramBot
from fsai.config import load_config
from fsai.fatsecret_client import FatSecretClient
from fsai.llm.factory import build_provider
from fsai.service import LoggerService
from fsai.store import Store


def main() -> None:
    load_dotenv()
    config = load_config()
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
    app.run_polling()


if __name__ == "__main__":
    main()
