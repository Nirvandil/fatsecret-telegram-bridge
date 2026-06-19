import os
from dataclasses import dataclass
from typing import Mapping


@dataclass
class Config:
    telegram_token: str
    owner_chat_id: int
    fatsecret_consumer_key: str
    fatsecret_consumer_secret: str
    fatsecret_access_token: str
    fatsecret_access_secret: str
    llm_provider: str
    llm_model: str
    llm_api_key: str
    db_path: str
    timezone: str
    meal_breakfast_start: int
    meal_lunch_start: int
    meal_dinner_start: int
    meal_dinner_end: int
    log_level: str
    poll_interval: float
    poll_timeout: int


def _required(env: Mapping[str, str], key: str) -> str:
    val = env.get(key)
    if not val:
        raise ValueError(f"Missing required env var: {key}")
    return val


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else os.environ
    return Config(
        telegram_token=_required(env, "TELEGRAM_TOKEN"),
        owner_chat_id=int(_required(env, "OWNER_CHAT_ID")),
        fatsecret_consumer_key=_required(env, "FATSECRET_CONSUMER_KEY"),
        fatsecret_consumer_secret=_required(env, "FATSECRET_CONSUMER_SECRET"),
        fatsecret_access_token=_required(env, "FATSECRET_ACCESS_TOKEN"),
        fatsecret_access_secret=_required(env, "FATSECRET_ACCESS_SECRET"),
        llm_provider=env.get("LLM_PROVIDER", "anthropic"),
        llm_model=env.get("LLM_MODEL", "claude-haiku-4-5"),
        llm_api_key=_required(env, "LLM_API_KEY"),
        db_path=env.get("DB_PATH", "fatsecret_telegram_bridge.sqlite3"),
        timezone=env.get("TZ", "UTC"),
        meal_breakfast_start=int(env.get("MEAL_BREAKFAST_START", "5")),
        meal_lunch_start=int(env.get("MEAL_LUNCH_START", "11")),
        meal_dinner_start=int(env.get("MEAL_DINNER_START", "16")),
        meal_dinner_end=int(env.get("MEAL_DINNER_END", "22")),
        log_level=env.get("LOG_LEVEL", "INFO"),
        poll_interval=float(env.get("POLL_INTERVAL", "0.0")),
        poll_timeout=int(env.get("POLL_TIMEOUT", "10")),
    )
